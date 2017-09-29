from __future__ import absolute_import

from django.core.exceptions import ObjectDoesNotExist

from sentry import tagstore
from sentry.api.base import DocSection
from sentry.api.bases.project import ProjectEndpoint
from sentry.api.exceptions import ResourceDoesNotExist
from sentry.api.paginator import DateTimePaginator
from sentry.api.serializers import serialize
from sentry.models import TagValue


class ProjectTagKeyValuesEndpoint(ProjectEndpoint):
    doc_section = DocSection.PROJECTS

    def get(self, request, project, key):
        """
        List a Tag's Values
        ```````````````````

        Return a list of values associated with this key.  The `query`
        parameter can be used to to perform a "contains" match on
        values.

        :pparam string organization_slug: the slug of the organization.
        :pparam string project_slug: the slug of the project.
        :pparam string key: the tag key to look up.
        :auth: required
        """
        lookup_key = tagstore.prefix_reserved_key(key)

        try:
            tagkey = tagstore.get_tag_key(project.id, lookup_key)
        except ObjectDoesNotExist:
            raise ResourceDoesNotExist

        queryset = TagValue.objects.filter(
            project_id=project.id,
            key=tagkey.key,
        )

        query = request.GET.get('query')
        if query:
            queryset = queryset.filter(value__contains=query)

        return self.paginate(
            request=request,
            queryset=queryset,
            order_by='-last_seen',
            paginator_cls=DateTimePaginator,
            on_results=lambda x: serialize(x, request.user),
        )
