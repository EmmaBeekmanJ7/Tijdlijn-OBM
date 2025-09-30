"""Contains all custom `Exceptions`"""


class TimelineNotGenerated(Exception):
    """The exception for when a "Timeline" object could not be generated"""

    pass

class DocumentsNotFound(Exception):
    """The exception for when no documents could be found or processed"""

    pass

class TimelineNotFound(Exception): 
    """The exception for when a timeline could not be found"""

    pass    

class TimelineNotInserted(Exception): 
    """The exception for when a timeline could not be inserted in OpenSearch"""

    pass    