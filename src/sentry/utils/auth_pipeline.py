from __future__ import absolute_import, print_function

__all__ = ['PipelineHelper']

import json
import logging

from django.http import HttpResponse

from sentry.utils.hashlib import md5_text
from sentry.web.helpers import render_to_response

DIALOG_RESPONSE = """
<!doctype html>
<html>
<body>
<script>
window.opener.postMessage({json}, document.origin);
window.close();
</script>
<noscript>Please wait...</noscript>
</body>
</html>
"""


class PipelineHelper(object):
    logger = logging.getLogger('sentry.pipeline')

    logger_event_prefix = 'pipeline'

    session_key = 'pipeline.setup'

    @classmethod
    def get_for_request(cls, request, provider_id):
        session = request.session.get(cls.session_key, {})
        if not session:
            cls.logger.error('{}.setup.missing-session-data'.format(
                cls.logger_event_prefix,
            ))
            return None

        instance = cls(
            request=request,
            provider_id=provider_id,
            **cls.params_from_session(request, session, provider_id)
        )
        if instance.signature != session['sig']:
            cls.logger.error('{}.setup.invalid-signature'.format(
                cls.logger_event_prefix,
            ))
            return None
        return instance

    @classmethod
    def params_from_session(cls, request, session, provider_id):
        if provider_id != session['pro']:
            cls.logger.error('{}.setup.invalid-provider'.format(
                cls.logger_event_prefix,
            ))
            return None

        if session['uid'] != (request.user.id if request.user.is_authenticated() else ''):
            cls.logger.error('{}.setup.invalid-uid'.format(
                cls.logger_event_prefix,
            ))
            return None

        return {
            'step': session['step'],
            'state': session['state'],
            'dialog': bool(session['dlg']),
            'provider_id': session['pro'],
        }

    @classmethod
    def initialize(cls, request, provider_id, dialog=False, **params):
        inst = cls(
            request=request,
            provider_id=provider_id,
            dialog=dialog,
            **params
        )
        inst.save_session()
        return inst

    def __init__(self, request, provider_id, step=0, state=None, dialog=False):
        self.request = request
        self.signature = md5_text(*[
            '{module}.{name}'.format(
                module=type(v).__module__,
                name=type(v).__name__,
            ) for v in self.pipeline
        ]).hexdigest()
        self.step = step
        self.state = state or {}
        self.dialog = dialog
        # order matters here
        self.provider = self.get_provider(provider_id)
        # build the pipeline last
        self.pipeline = self.get_pipeline()

    def get_pipeline(self):
        return self.provider.get_pipeline()

    def get_provider(self, provider_id):
        raise NotImplementedError

    def get_session_state(self):
        return {
            'uid': self.request.user.id if self.request.user.is_authenticated() else '',
            'org': self.organization.id,
            'pro': self.provider.id,
            'int': self.integration.id if self.integration else '',
            'sig': self.signature,
            'step': self.step,
            'state': self.state,
            'dlg': int(self.dialog),
        }

    def save_session(self):
        self.request.session[self.session_key] = self.get_session_state()
        self.request.session.modified = True

    def get_redirect_url(self):
        raise NotImplementedError

    def clear_session(self):
        if self.session_key in self.request.session:
            del self.request.session[self.session_key]
            self.request.session.modified = True

    def current_step(self):
        """
        Render the current step.
        """
        if self.step == len(self.pipeline):
            return self.finish_pipeline()
        return self.pipeline[self.step].dispatch(
            request=self.request,
            helper=self,
        )

    def next_step(self):
        """
        Render the next step.
        """
        self.step += 1
        self.save_session()
        return self.current_step()

    def finish_pipeline(self):
        raise NotImplementedError

    def get_default_context(self):
        return {
            'provider': self.provider,
        }

    def respond(self, template, context=None, status=200):
        default_context = self.get_default_context()
        if context:
            default_context.update(context)
        return render_to_response(template, default_context, self.request, status=status)

    def error(self, message):
        # TODO(dcramer): this needs to handle the dialog
        self.clear_session()
        return self.dialog_response({'detail': message}, False)

    def bind_state(self, key, value):
        self.state[key] = value
        self.save_session()

    def fetch_state(self, key):
        return self.state.get(key)

    def standard_response(self, success):
        raise NotImplementedError

    def dialog_response(self, data, success):
        assert self.dialog
        return HttpResponse(
            DIALOG_RESPONSE.format(
                json=json.dumps({
                    'success': success,
                    'data': data,
                })
            ),
            content_type='text/html',
        )
