(() => {
    'use strict';

    const config = window.operatorSignerConfig || {};
    const apiBase = String(config.url || '').replace(/\/$/, '');
    const tokenKey = 'workspace.operatorSigner.token';
    const directoryKey = 'workspace.operatorSigner.directory';

    function storageGet(key) {
        try {
            return window.sessionStorage.getItem(key) || '';
        } catch (_) {
            return '';
        }
    }

    function storageSet(key, value) {
        try {
            if (value) {
                window.sessionStorage.setItem(key, value);
            } else {
                window.sessionStorage.removeItem(key);
            }
        } catch (_) {
            // Session storage — только удобство. Signer продолжит работать без него.
        }
    }

    function token() {
        const input = document.getElementById('operator-signer-token');
        return input ? input.value.trim() : '';
    }

    function directory() {
        const input = document.getElementById('operator-signer-directory');
        return input ? input.value.trim() : '';
    }

    function remember() {
        storageSet(tokenKey, token());
        storageSet(directoryKey, directory());
    }

    function restore() {
        const tokenInput = document.getElementById('operator-signer-token');
        const directoryInput = document.getElementById('operator-signer-directory');
        if (tokenInput && !tokenInput.value) {
            tokenInput.value = storageGet(tokenKey);
        }
        if (directoryInput && !directoryInput.value) {
            directoryInput.value = storageGet(directoryKey);
        }
    }

    function setStatus(message, state = 'idle') {
        const node = document.getElementById('operator-signer-status');
        if (!node) return;
        node.textContent = message;
        node.dataset.state = state;
    }

    async function request(path, options = {}) {
        if (!apiBase) {
            throw new Error('URL локального signer не настроен.');
        }
        const pairingToken = token();
        if (!pairingToken) {
            throw new Error('Введите код подключения, который показал локальный signer.');
        }

        const init = {
            method: options.method || 'POST',
            mode: 'cors',
            cache: 'no-store',
            credentials: 'omit',
            targetAddressSpace: 'loopback',
            headers: {
                'Authorization': 'Bearer ' + pairingToken,
            },
        };
        if (options.body !== undefined) {
            init.headers['Content-Type'] = 'application/json';
            init.body = JSON.stringify(options.body);
        }

        let response;
        try {
            response = await fetch(apiBase + path, init);
        } catch (_) {
            throw new Error(
                'Локальный signer недоступен. Запустите tools/operator-signer/start.ps1 на этом ПК, не закрывайте его окно и разрешите браузеру доступ к loopback/локальной сети, если он запросит разрешение.'
            );
        }

        let payload = null;
        try {
            payload = await response.json();
        } catch (_) {
            // Ни private key, ни локальный путь сюда не попадают; сообщение только диагностическое.
        }

        if (!response.ok || !payload || payload.status === 'error') {
            throw new Error(
                (payload && payload.message)
                    ? payload.message
                    : 'Локальный signer вернул ошибку HTTP ' + response.status + '.'
            );
        }
        return payload;
    }

    async function ping() {
        remember();
        const payload = await request('/status', {method: 'GET'});
        setStatus(
            'Signer подключён · PHP ' + payload.php_version + ' · ' + payload.os_family,
            'ok'
        );
        return payload;
    }

    async function selectDirectory() {
        await ping();
        setStatus('Открываю системный диалог выбора папки…', 'working');
        const payload = await request('/select-directory', {method: 'POST'});
        if (payload.cancelled || !payload.directory) {
            setStatus('Выбор папки отменён.', 'idle');
            return '';
        }
        const input = document.getElementById('operator-signer-directory');
        if (input) {
            input.value = payload.directory;
        }
        remember();
        setStatus('Папка выбрана: ' + payload.directory, 'ok');
        return payload.directory;
    }

    async function scan() {
        const localDirectory = directory();
        if (!localDirectory) {
            throw new Error('Сначала выберите папку с ключами через системный диалог.');
        }
        remember();
        await ping();
        const payload = await request('/scan', {
            body: {directory: localDirectory},
        });
        return payload.keys || [];
    }

    function registry(kind) {
        return kind === 'license'
            ? (config.licenseTrustedKeys || {})
            : (config.updateTrustedKeys || {});
    }

    function findMatchingKey(keys, kind, keyId) {
        const expected = registry(kind)[keyId];
        if (!expected) {
            throw new Error('Выбранный key_id отсутствует в public trust registry сайта.');
        }
        const match = keys.find(
            item => item.type === kind && item.public_key === expected
        );
        if (!match) {
            throw new Error(
                'В выбранной папке не найден ' + kind
                + ' private key, соответствующий trust root «' + keyId + '».'
            );
        }
        return {key: match, expectedPublicKey: expected};
    }

    async function scanAndMatch(kind, keyId) {
        setStatus('Проверяю локальную папку и public fingerprint…', 'working');
        const keys = await scan();
        const matched = findMatchingKey(keys, kind, keyId);
        setStatus(
            'Ключ найден: ' + matched.key.file
            + ' · fingerprint ' + matched.key.fingerprint,
            'ok'
        );
        return matched;
    }

    function utcTimestamp(value) {
        const text = String(value || '').trim();
        if (!text) return null;
        const milliseconds = Date.parse(text + ':00Z');
        if (!Number.isFinite(milliseconds)) {
            throw new Error('Некорректная UTC дата: ' + text);
        }
        return Math.floor(milliseconds / 1000);
    }

    function nullablePositiveInt(value, label) {
        const text = String(value || '').trim();
        if (!text) return null;
        if (!/^[1-9][0-9]*$/.test(text)) {
            throw new Error(label + ' должен быть положительным целым числом.');
        }
        return Number.parseInt(text, 10);
    }

    async function signLicense(params) {
        const matched = await scanAndMatch('license', params.keyId);
        setStatus('Подписываю лицензию локальным ключом…', 'working');
        const payload = await request('/sign-license', {
            body: {
                directory: directory(),
                file: matched.key.file,
                key_id: params.keyId,
                expected_public_key: matched.expectedPublicKey,
                license: params.license,
            },
        });
        setStatus('Лицензия подписана на этом компьютере. Отправляю только wo1 token на сервер…', 'ok');
        return payload.token;
    }

    async function signManifest(params) {
        const matched = await scanAndMatch('update', params.keyId);
        setStatus('Подписываю update manifest локальным ключом…', 'working');
        const payload = await request('/sign-manifest', {
            body: {
                directory: directory(),
                file: matched.key.file,
                key_id: params.keyId,
                expected_public_key: matched.expectedPublicKey,
                manifest: params.manifest,
            },
        });
        setStatus('Manifest подписан на этом компьютере. Отправляю только wou1 signature на сервер…', 'ok');
        return payload.signature;
    }

    function submitHidden(action, fields) {
        const form = document.createElement('form');
        form.method = 'post';
        form.action = action;
        form.hidden = true;
        Object.entries(fields).forEach(([name, value]) => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = name;
            input.value = value == null ? '' : String(value);
            form.appendChild(input);
        });
        document.body.appendChild(form);
        form.submit();
    }

    document.addEventListener('DOMContentLoaded', restore);

    window.OperatorSigner = {
        ping,
        selectDirectory,
        scanAndMatch,
        signLicense,
        signManifest,
        utcTimestamp,
        nullablePositiveInt,
        setStatus,
        submitHidden,
        remember,
    };
})();
