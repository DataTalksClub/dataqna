from unittest.mock import Mock

import pytest

from dataqna import config, security


def test_session_signing_reads_verbatim_store_value(monkeypatch):
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    monkeypatch.setattr(security, '_secret_cache', None)
    client = Mock()
    client.read.return_value = {'value': '{"signing_secret":"fixture-signing-key"}'}
    factory = Mock(return_value=client)
    monkeypatch.setattr(security, 'SecretReader', factory)
    monkeypatch.setattr(config, 'SECRETS_KEY_ID', 'fixture-key')
    token = security.sign({'kind': 'test', 'exp': 9999999999})
    assert security.verify(token, 'test')['kind'] == 'test'
    client.read.assert_called_once_with('dataqna.session')
    factory.assert_called_once_with(table_name='dataops-v1-secrets', key_id='fixture-key', region='eu-west-1')


def test_reader_denial_fails_closed(monkeypatch):
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    monkeypatch.setattr(security, '_secret_cache', None)
    client = Mock()
    client.read.side_effect = PermissionError('denied')
    monkeypatch.setattr(security, 'SecretReader', Mock(return_value=client))
    with pytest.raises(PermissionError):
        security.secret()
