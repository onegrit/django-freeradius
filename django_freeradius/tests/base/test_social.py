from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.authtoken.models import Token

from ... import settings as app_settings


class BaseTestSocial(object):
    view_name = 'freeradius:redirect_cp'
    auth_header = 'Bearer {}'.format(app_settings.API_TOKEN)

    def get_url(self):
        return reverse(self.view_name)

    def _create_social_user(self):
        u = get_user_model().objects.create(username='socialuser',
                                            email='test@test.org')
        u.set_unusable_password()
        u.save()
        sa = SocialAccount(user=u,
                           provider='facebook',
                           uid='12345',
                           extra_data='{}')
        sa.full_clean()
        sa.save()
        return u

    def test_redirect_cp_400(self):
        url = self.get_url()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 400)

    def test_redirect_cp_403(self):
        url = self.get_url()
        r = self.client.get(url, {'cp': 'http://wifi.openwisp.org/cp'})
        self.assertEqual(r.status_code, 403)

    def test_redirect_cp_301(self):
        u = self._create_social_user()
        self.client.force_login(u)
        url = self.get_url()
        r = self.client.get(url, {'cp': 'http://wifi.openwisp.org/cp'})
        self.assertEqual(r.status_code, 302)
        qs = Token.objects.filter(user=u)
        self.assertEqual(qs.count(), 1)
        token = qs.first()
        querystring = 'username={}&token={}'.format(u.username,
                                                    token.key)
        self.assertIn(querystring, r.url)

    def test_authorize_using_user_token_200(self):
        self.test_redirect_cp_301()
        token = Token.objects.filter(user__username='socialuser').first()
        self.assertIsNotNone(token)
        response = self.client.post(reverse('freeradius:authorize'),
                                    {'username': 'socialuser', 'password': token.key},
                                    HTTP_AUTHORIZATION=self.auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'control:Auth-Type': 'Accept'})

    def test_authorize_using_user_token_403(self):
        self.test_redirect_cp_301()
        token = Token.objects.filter(user__username='socialuser').first()
        self.assertIsNotNone(token)
        response = self.client.post(reverse('freeradius:authorize'),
                                    {'username': 'socialuser', 'password': 'WRONG'},
                                    HTTP_AUTHORIZATION=self.auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data)
