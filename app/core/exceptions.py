class RetryableAPIError(Exception):
    pass


class RetryableEmbeddingError(Exception):
    """Raised when embedding API calls should be retried."""
