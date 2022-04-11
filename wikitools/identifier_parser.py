import typing

from wikitools import link_parser

ID_PREFIXES = {'#', 'id='}


def extract_identifier(s: str) -> typing.Set[str]:
    """
    Attempt to extract an identifier from a line. These are used in link fragments to skip to certain lines of an article. The following are recognised:
        - Implicit identifiers, which are generated by headings
        - Explicit identifier tags: {#i-den-ti-fi-er} or {id=i-den-ti-fi-er}
            (placed in the beginning or the end of the line: https://github.com/ppy/osu-web/issues/8057)

    This function doesn't recognise HTML comments and code blocks and will extract identifiers from these as well.
    The burden of checking for the comments and code blocks lies on the caller.
    """

    for i in range(len(s)):
        if s[i] == '{':
            # could be an identifier -- check if there are any meaningful prefixes ahead
            id_start = None
            for prefix in ID_PREFIXES:
                id_start = i + 1 + len(prefix)
                if id_start >= len(s) or s[i + 1: id_start] != prefix:
                    continue

                j = id_start
                while j < len(s) and s[j] != '}':
                    j += 1
                if j < len(s) and s[j] == '}':
                    return s[id_start: j]

    # skip regular lines and alt_texts (no one refers to them)
    if not s.startswith('#') or s.startswith('# '):
        return

    # skip to the actual heading
    j = 0
    while j < len(s) and s[j] in ('#', ' '):
        j += 1

    # headings can contain figures or formatting, but ASC disallows the latter.
    # XXX(TicClick): I am assuming that there is only ONE figure per heading.
    link = link_parser.find_link(s, j)
    if link is not None:
        # before link.start, there is an exclamation mark
        if s[link.start - 1] == '!':
            heading = s[j: link.start - 1] + s[link.end + 1:]
        else:
            # People/The_Team/Account_support_team has e-mail addresses WITH LINKS IN THEM as headings
            heading = s[j: link.start] + link.alt_text + s[link.end + 1:]
    else:
        heading = s[j:]

    return "-".join((word.lower() for word in heading.strip().split()))
