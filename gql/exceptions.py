class GQLSyntaxError(Exception):
    """A problem with the GQL query or schema syntax"""

class GQLServerError(Exception):
    """Errors which should be explicitly handled by the calling code"""
