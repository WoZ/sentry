from __future__ import absolute_import, print_function

__all__ = ['IntegrationPipelineHelper']

import logging

from django.db import IntegrityError, transaction

from sentry.api.serializers import serialize
from sentry.models import (
    Identity, IdentityProvider, IdentityStatus, Integration, Organization,
    UserIdentity
)
from sentry.utils.auth_pipeline import PipelineHelper
from sentry.utils.http import absolute_uri

from . import default_manager


class IntegrationPipelineHelper(PipelineHelper):
    logger = logging.getLogger('sentry.integrations')

    logger_event_prefix = 'integrations'

    session_key = 'integration.setup'

    @classmethod
    def params_from_session(cls, request, session, provider_id):
        # TODO(dcramer): enforce access check
        params = super(IntegrationPipelineHelper, cls).params_from_session(
            request, session, provider_id)

        organization = Organization.objects.get(
            id=session['org'],
        )

        if session.get('int'):
            integration = Integration.objects.get(
                id=session['int'],
                organization_id=organization.id,
            )
        else:
            integration = None

        params.update({
            'integration': integration,
            'organization': organization,
        })
        return params

    def __init__(self, organization, integration=None, **kwargs):
        super(IntegrationPipelineHelper, self).__init__(**kwargs)
        self.organization = organization
        self.integration = integration

    def get_default_context(self):
        context = super(IntegrationPipelineHelper, self).get_default_context()
        context['organization'] = self.organization
        return context

    def get_redirect_url(self):
        return absolute_uri('/extensions/{}/setup/'.format(
            self.provider.id,
        ))

    def get_provider(self, provider_id):
        return default_manager.get(provider_id)

    def get_session_state(self):
        result = super(IntegrationPipelineHelper, self).get_session_state()
        result.update({
            'org': self.organization.id,
            'int': self.integration.id if self.integration else '',
        })
        return result

    def finish_pipeline(self):
        data = self.provider.build_integration(self.state)

        if self.integration:
            assert data['external_id'] == self.integration.external_id
            self.integration.update(
                metadata=data.get('metadata', {}),
                name=data.get('name', self.provider.name),
            )
        else:
            defaults = {
                'metadata': data.get('metadata', {}),
                'name': data.get('name', data['external_id']),
            }
            self.integration, created = Integration.objects.get_or_create(
                provider=self.provider.id,
                external_id=data['external_id'],
                defaults=defaults
            )
            if not created:
                self.integration.update(**defaults)
            self.integration.add_organization(self.organization.id)

        id_config = data.get('identity')
        if id_config:
            idp = IdentityProvider.get(id_config['type'], id_config['instance'])
            identity, created = Identity.objects.get_or_create(
                idp=idp,
                external_id=id_config['external_id'],
                defaults={
                    'status': IdentityStatus.VALID,
                    'scopes': id_config['scopes'],
                    'data': id_config['data'],
                },
            )
            if not created:
                if identity.status != IdentityStatus.VALID:
                    identity.update(status=IdentityStatus.VALID)
            try:
                with transaction.atomic():
                    UserIdentity.objects.create(
                        user=self.request.user,
                        identity=identity,
                    )
            except IntegrityError:
                pass

        self.clear_session()

        if self.dialog:
            return self.dialog_response(
                serialize(self.integration, self.request.user),
                True,
            )
        return self.standard_response(True)
