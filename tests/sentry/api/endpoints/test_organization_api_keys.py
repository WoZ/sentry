from __future__ import absolute_import

from django.core.urlresolvers import reverse

from sentry.models import ApiKey
from sentry.testutils import APITestCase

DEFAULT_SCOPES = [
    'project:read',
    'event:read',
    'team:read',
    'org:read',
    'member:read',
]


class OrganizationApiKeys(APITestCase):
    def test_org_admin_can_access(self):
        self.login_as(user=self.user)

        organization = self.create_organization(name='foo', owner=self.user)

        path = reverse(
            'sentry-api-0-organization-api-keys',
            args=[organization.slug]
        )

        resp = self.client.get(path)

        assert resp.status_code == 200

    def test_member_no_access(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        user = self.create_user('bar@example.com')
        self.create_member(
            organization=organization,
            user=user,
            role='member',
        )

        path = reverse(
            'sentry-api-0-organization-api-keys',
            args=[organization.slug]
        )

        self.login_as(user)

        resp = self.client.get(path)

        assert resp.status_code == 403

    def test_admin_can_access(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        admin_user = self.create_user('admin@example.com', is_superuser=True)
        self.create_member(
            organization=organization,
            user=admin_user,
            role='admin',
        )

        path = reverse(
            'sentry-api-0-organization-api-keys',
            args=[organization.slug]
        )

        self.login_as(admin_user)

        resp = self.client.get(path)

        assert resp.status_code == 200

    def test_org_admin_can_create(self):
        self.login_as(user=self.user)

        organization = self.create_organization(name='foo', owner=self.user)

        path = reverse(
            'sentry-api-0-organization-api-keys',
            args=[organization.slug]
        )

        resp = self.client.post(path)

        assert resp.status_code == 200
        assert resp.data.get('label') == 'Default'

    def test_member_no_create(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        user = self.create_user('bar@example.com')
        self.create_member(
            organization=organization,
            user=user,
            role='member',
        )

        path = reverse(
            'sentry-api-0-organization-api-keys',
            args=[organization.slug]
        )

        self.login_as(user)

        resp = self.client.post(path)

        assert resp.status_code == 403


class OrganizationApiKeyDetails(APITestCase):
    def test_api_key_no_exist(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        path = reverse(
            'sentry-api-0-organization-api-key-details',
            args=[organization.slug, 2]
        )

        resp = self.client.get(path)

        assert resp.status_code == 404

    def test_get_api_details(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        api_key = ApiKey.objects.create(
            organization=organization,
            scope_list=DEFAULT_SCOPES
        )

        path = reverse(
            'sentry-api-0-organization-api-key-details',
            args=[organization.slug, api_key.id]
        )

        resp = self.client.get(path)

        assert resp.status_code == 200
        assert resp.data.get('id') == api_key.id

    def test_update_api_key_details(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        api_key = ApiKey.objects.create(
            organization=organization,
            scope_list=DEFAULT_SCOPES
        )

        path = reverse(
            'sentry-api-0-organization-api-key-details',
            args=[organization.slug, api_key.id]
        )

        resp = self.client.put(path, data={'label': 'New Label', 'allowed_origins': 'sentry.io'})

        assert resp.status_code == 200

        api_key = ApiKey.objects.get(
            id=api_key.id,
            organization_id=organization.id,
        )

        assert api_key.label == 'New Label'
        assert api_key.allowed_origins == 'sentry.io'

    def test_can_delete_api_key(self):
        self.login_as(user=self.user)
        organization = self.create_organization(name='foo', owner=self.user)

        api_key = ApiKey.objects.create(
            organization=organization,
            scope_list=DEFAULT_SCOPES
        )

        path = reverse(
            'sentry-api-0-organization-api-key-details',
            args=[organization.slug, api_key.id]
        )

        resp = self.client.delete(path)

        assert resp.status_code == 202

        # check to make sure it's deleted
        resp = self.client.get(path)
        assert resp.status_code == 404