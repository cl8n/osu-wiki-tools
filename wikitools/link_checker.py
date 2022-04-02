import os
import typing

from wikitools import redirect_parser, reference_parser, errors, link_parser, article_parser


class DetailedError(typing.NamedTuple):
    link: link_parser.Link
    error: errors.LinkError


def extract_tail(path: str) -> str:
    """
    Given a path in a file system, return its tail (everything past the first non-root slash). Examples:
        - /wiki/Beatmap/Category -> Beatmap/Category
        - img/users/2.png -> users/2.png
    """
    return path[path.find('/', 1) + 1:]


def check_link(
    article: article_parser.Article, link_: typing.Union[link_parser.Link, reference_parser.Reference],
    redirects: redirect_parser.Redirects, references: reference_parser.References,
    all_articles: typing.Dict[str, article_parser.Article]
) -> typing.Optional[errors.LinkError]:
    """
    Verify that the link is valid:
        - External links are always assumed valid, since we can't just issue HTTP requests left and right
        - For Markdown references, there exists a dereferencing line with [reference_name]: /lo/ca/ti/on
        - Direct internal links, as well as redirects, must point to existing article files
        - Relative links are parsed under the assumption that they are located inside the current article's directory
    """

    # resolve the link, if possible
    link = link_ if isinstance(link_, reference_parser.Reference) else link_.resolve(references)
    if link is None:
        return errors.MissingReference(link_.raw_location)

    location = link.parsed_location.path
    parsed_location = link.parsed_location

    # some external link; don't care
    if parsed_location.scheme:
        return

    # domain is non-empty, but the link is internal?
    if parsed_location.netloc:
        raise RuntimeError(f"Unhandled link type: {parsed_location}")

    # convert a relative wikilink to absolute
    if not location.startswith("/wiki/"):
        current_article_dir = os.path.relpath(article.directory, 'wiki/')
        location = f"/wiki/{current_article_dir}/{location}"

    target = location[1:]
    # no article? could be a redirect check for a redirect
    if not os.path.exists(target):
        redirect_source = extract_tail(location)
        try:
            redirect_destination, redirect_line_no = redirects[redirect_source.lower()]
        except KeyError:
            return errors.LinkNotFound(redirect_source)

        target = os.path.join('wiki', redirect_destination)
        if not os.path.exists(target):
            return errors.BrokenRedirect(redirect_source, redirect_line_no, redirect_destination)

    # link to an article in general, article exists -> good
    if not parsed_location.fragment:
        return

    # link to a section -> need to find the target article; it could be a translation
    # XXX(TicClick): this part assumes there is always an English version of the article in a folder
    target_file = os.path.join(target, article.filename)
    is_translation_available = article.filename != 'en.md' and os.path.exists(target_file)
    if not is_translation_available:
        target_file = os.path.join(target, 'en.md')
    if target_file not in all_articles:
        # this is safe to do since the caller iterates over a copy of all_articles -> we can modify it as we wish
        all_articles[target_file] = article_parser.parse(target_file)
    target_article = all_articles[target_file]
    if parsed_location.fragment not in target_article.identifiers:
        return errors.MissingIdentifier(target_file, parsed_location.fragment, translation_available=is_translation_available)

    return


def check_article(article, redirects: redirect_parser.Redirects, all_articles: typing.Dict[str, article_parser.Article]):
    """
    Try resolving links in the article either to another articles, or files.
    """

    result = {}
    for lineno, line in article.lines.items():
        for link in line.links:
            error = check_link(article, link, redirects, article.references, all_articles)
            if error is not None:
                result.setdefault(lineno, []).append(DetailedError(link=link, error=error))

    return result
