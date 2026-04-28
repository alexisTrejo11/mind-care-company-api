from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination that allows clients to customize page_size via
    'page_size' query parameter while enforcing a maximum limit.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
