<?php

declare(strict_types=1);

/**
 * Локальный signer Workspace Organizer.
 *
 * Скрипт запускается только на ПК оператора через встроенный PHP server и
 * принимает запросы исключительно с loopback-интерфейса. Private keys никогда
 * не отправляются в jsinteractive.ru: наружу возвращаются только public key,
 * fingerprint и готовые подписи/токены.
 */

const SIGNER_API_VERSION = 1;
const LICENSE_SECRET_PREFIX = 'wo-ed25519-secret-v1:';
const UPDATE_SECRET_PREFIX = 'wo-update-ed25519-secret-v1:';
const UPDATE_SIGNATURE_DOMAIN = "WorkspaceOrganizerUpdateManifest/v1\n";
const MAX_KEY_BYTES = 4096;
const MAX_MANIFEST_BYTES = 131072;

/** @return never */
function signerRespond(array $payload, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    echo json_encode(
        $payload,
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
    );
    exit;
}

/** @return never */
function signerFail(string $message, string $code = 'invalid_request', int $status = 400): never
{
    signerRespond([
        'status' => 'error',
        'code' => $code,
        'message' => $message,
    ], $status);
}

function signerBase64UrlEncode(string $value): string
{
    return rtrim(strtr(base64_encode($value), '+/', '-_'), '=');
}

function signerBase64UrlDecode(string $value): ?string
{
    if ($value === '' || preg_match('/^[A-Za-z0-9_-]+$/D', $value) !== 1) {
        return null;
    }
    $padding = (4 - (strlen($value) % 4)) % 4;
    $decoded = base64_decode(
        strtr($value, '-_', '+/') . str_repeat('=', $padding),
        true
    );
    return $decoded === false ? null : $decoded;
}

function signerRequireRuntime(): void
{
    if (!extension_loaded('sodium')) {
        signerFail(
            'В локальном PHP не загружено расширение sodium.',
            'sodium_missing',
            503
        );
    }

    $remote = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
    if (!in_array($remote, ['127.0.0.1', '::1'], true)) {
        signerFail(
            'Локальный signer принимает запросы только с этого компьютера.',
            'loopback_required',
            403
        );
    }
}

function signerApplyCors(): void
{
    $allowedOrigin = trim((string) getenv('OPERATOR_SIGNER_ORIGIN'));
    if ($allowedOrigin === '') {
        $allowedOrigin = 'https://jsinteractive.ru';
    }

    $origin = trim((string) ($_SERVER['HTTP_ORIGIN'] ?? ''));
    if ($origin === '' || !hash_equals($allowedOrigin, $origin)) {
        signerFail(
            'Origin страницы не разрешён локальным signer.',
            'origin_denied',
            403
        );
    }

    header('Access-Control-Allow-Origin: ' . $allowedOrigin);
    header('Vary: Origin');
    header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
    header('Access-Control-Allow-Headers: Authorization, Content-Type');
    header('Access-Control-Max-Age: 600');

    if (
        strtolower((string) ($_SERVER['HTTP_ACCESS_CONTROL_REQUEST_PRIVATE_NETWORK'] ?? ''))
        === 'true'
    ) {
        header('Access-Control-Allow-Private-Network: true');
    }

    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
        http_response_code(204);
        exit;
    }
}

/**
 * @param list<string> $command
 * @return array{code:int,stdout:string,stderr:string}
 */
function signerRunProcess(array $command): array
{
    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $process = @proc_open(
        $command,
        $descriptors,
        $pipes,
        null,
        null,
        ['bypass_shell' => true]
    );
    if (!is_resource($process)) {
        signerFail(
            'Не удалось открыть системный диалог выбора папки.',
            'directory_picker_unavailable',
            503
        );
    }

    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $code = proc_close($process);

    return [
        'code' => $code,
        'stdout' => is_string($stdout) ? trim($stdout) : '',
        'stderr' => is_string($stderr) ? trim($stderr) : '',
    ];
}

function signerFindExecutable(string $name): ?string
{
    $path = (string) getenv('PATH');
    foreach (explode(PATH_SEPARATOR, $path) as $directory) {
        $directory = trim($directory);
        if ($directory === '') {
            continue;
        }
        $candidate = rtrim($directory, DIRECTORY_SEPARATOR)
            . DIRECTORY_SEPARATOR . $name;
        if (is_file($candidate) && is_executable($candidate)) {
            return $candidate;
        }
    }
    return null;
}

function signerSelectDirectory(): ?string
{
    if (PHP_OS_FAMILY === 'Windows') {
        $script = <<<'POWERSHELL'
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Выберите папку с ключами Workspace Organizer'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
    exit 0
}
exit 2
POWERSHELL;
        $result = signerRunProcess([
            'powershell.exe',
            '-NoProfile',
            '-STA',
            '-ExecutionPolicy',
            'Bypass',
            '-Command',
            $script,
        ]);
    } elseif (PHP_OS_FAMILY === 'Darwin') {
        $result = signerRunProcess([
            '/usr/bin/osascript',
            '-e',
            'POSIX path of (choose folder with prompt "Выберите папку с ключами Workspace Organizer")',
        ]);
    } else {
        $zenity = signerFindExecutable('zenity');
        $kdialog = signerFindExecutable('kdialog');
        if ($zenity !== null) {
            $result = signerRunProcess([
                $zenity,
                '--file-selection',
                '--directory',
                '--title=Выберите папку с ключами Workspace Organizer',
            ]);
        } elseif ($kdialog !== null) {
            $result = signerRunProcess([
                $kdialog,
                '--getexistingdirectory',
                '.',
                '--title',
                'Выберите папку с ключами Workspace Organizer',
            ]);
        } else {
            signerFail(
                'Для системного диалога на Linux нужен zenity или kdialog.',
                'directory_picker_unavailable',
                503
            );
        }
    }

    if ($result['code'] !== 0 || $result['stdout'] === '') {
        return null;
    }

    return signerResolveDirectory($result['stdout']);
}


function signerRequireToken(): void
{
    $expected = trim((string) getenv('OPERATOR_SIGNER_TOKEN'));
    if ($expected === '' || preg_match('/^[0-9a-f]{32,128}$/D', $expected) !== 1) {
        signerFail(
            'Локальный signer запущен без pairing token.',
            'signer_misconfigured',
            503
        );
    }

    $authorization = trim((string) ($_SERVER['HTTP_AUTHORIZATION'] ?? ''));
    if (preg_match('/^Bearer ([0-9a-f]{32,128})$/D', $authorization, $match) !== 1) {
        signerFail('Требуется код подключения signer.', 'authentication_required', 401);
    }

    if (!hash_equals($expected, $match[1])) {
        signerFail('Неверный код подключения signer.', 'authentication_required', 401);
    }
}

/** @return array<string,mixed> */
function signerJsonBody(): array
{
    $length = (int) ($_SERVER['CONTENT_LENGTH'] ?? 0);
    if ($length < 1 || $length > 262144) {
        signerFail('Некорректный размер запроса.');
    }

    $raw = file_get_contents('php://input');
    if (!is_string($raw)) {
        signerFail('Не удалось прочитать запрос.');
    }

    try {
        $data = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
    } catch (JsonException $e) {
        signerFail('Запрос должен быть корректным JSON.');
    }

    if (!is_array($data)) {
        signerFail('JSON body должен быть объектом.');
    }
    return $data;
}

function signerIsAbsolutePath(string $path): bool
{
    return str_starts_with($path, '/')
        || str_starts_with($path, '\\\\')
        || preg_match('/^[A-Za-z]:[\\\\\/]/D', $path) === 1;
}

function signerResolveDirectory(string $path): string
{
    $path = trim($path);
    if ($path === '' || strlen($path) > 2048 || !signerIsAbsolutePath($path)) {
        signerFail('Укажите абсолютный путь к локальной папке с ключами.');
    }

    $resolved = realpath($path);
    if (!is_string($resolved) || !is_dir($resolved)) {
        signerFail('Папка с ключами не найдена на этом компьютере.', 'directory_not_found', 404);
    }
    return $resolved;
}

function signerNormalizePath(string $path): string
{
    $path = str_replace('\\', '/', $path);
    if (preg_match('/^[A-Za-z]:/', $path) === 1) {
        $path = strtolower($path[0]) . substr($path, 1);
    }
    return rtrim($path, '/');
}

function signerResolveKeyFile(string $directory, string $file): string
{
    $directory = signerResolveDirectory($directory);
    $file = trim($file);
    if (
        $file === ''
        || strlen($file) > 255
        || basename($file) !== $file
        || str_contains($file, '/')
        || str_contains($file, '\\')
    ) {
        signerFail('Некорректное имя key file.');
    }

    $candidate = $directory . DIRECTORY_SEPARATOR . $file;
    if (is_link($candidate)) {
        signerFail('Symlink для private key запрещён.', 'unsafe_key_file', 403);
    }

    $resolved = realpath($candidate);
    if (!is_string($resolved) || !is_file($resolved)) {
        signerFail('Private key file не найден.', 'key_not_found', 404);
    }

    if (
        signerNormalizePath(dirname($resolved))
        !== signerNormalizePath($directory)
    ) {
        signerFail('Private key вышел за пределы выбранной папки.', 'unsafe_key_file', 403);
    }

    $size = filesize($resolved);
    if (!is_int($size) || $size < 1 || $size > MAX_KEY_BYTES) {
        signerFail('Private key file имеет недопустимый размер.', 'invalid_key_file');
    }

    if (PHP_OS_FAMILY !== 'Windows') {
        $permissions = fileperms($resolved);
        if ($permissions !== false && (($permissions & 0077) !== 0)) {
            signerFail(
                'Private key file должен иметь права 0600.',
                'unsafe_key_permissions',
                403
            );
        }
    }

    return $resolved;
}

/**
 * @return array{type:string,secret:string,public:string,file:string}
 */
function signerLoadKey(string $directory, string $file): array
{
    $resolved = signerResolveKeyFile($directory, $file);
    $content = file_get_contents($resolved);
    if (!is_string($content)) {
        signerFail('Не удалось прочитать private key file.', 'key_unreadable', 503);
    }
    $content = trim($content);

    $type = '';
    $encoded = '';
    if (str_starts_with($content, LICENSE_SECRET_PREFIX)) {
        $type = 'license';
        $encoded = substr($content, strlen(LICENSE_SECRET_PREFIX));
    } elseif (str_starts_with($content, UPDATE_SECRET_PREFIX)) {
        $type = 'update';
        $encoded = substr($content, strlen(UPDATE_SECRET_PREFIX));
    } else {
        signerFail('Файл не является Workspace Organizer signing key.', 'unsupported_key');
    }

    $secret = signerBase64UrlDecode($encoded);
    sodium_memzero($content);
    if (!is_string($secret) || strlen($secret) !== SODIUM_CRYPTO_SIGN_SECRETKEYBYTES) {
        signerFail('Private key имеет некорректный Ed25519 формат.', 'invalid_key');
    }

    $public = sodium_crypto_sign_publickey_from_secretkey($secret);
    $embeddedPublic = substr($secret, -SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES);
    if (!hash_equals($public, $embeddedPublic)) {
        sodium_memzero($secret);
        signerFail('Private key содержит несогласованную Ed25519 keypair.', 'invalid_key');
    }

    return [
        'type' => $type,
        'secret' => $secret,
        'public' => $public,
        'file' => basename($resolved),
    ];
}

/** @return list<array<string,mixed>> */
function signerScanDirectory(string $directory): array
{
    $directory = signerResolveDirectory($directory);
    $entries = scandir($directory);
    if (!is_array($entries)) {
        signerFail('Не удалось просмотреть папку с ключами.', 'directory_unreadable', 503);
    }

    $keys = [];
    foreach ($entries as $entry) {
        if ($entry === '.' || $entry === '..') {
            continue;
        }

        $candidate = $directory . DIRECTORY_SEPARATOR . $entry;
        if (!is_file($candidate) || is_link($candidate)) {
            continue;
        }

        $size = filesize($candidate);
        if (!is_int($size) || $size < 1 || $size > MAX_KEY_BYTES) {
            continue;
        }

        $content = @file_get_contents($candidate);
        if (!is_string($content)) {
            continue;
        }
        $content = trim($content);

        $type = null;
        $encoded = null;
        if (str_starts_with($content, LICENSE_SECRET_PREFIX)) {
            $type = 'license';
            $encoded = substr($content, strlen(LICENSE_SECRET_PREFIX));
        } elseif (str_starts_with($content, UPDATE_SECRET_PREFIX)) {
            $type = 'update';
            $encoded = substr($content, strlen(UPDATE_SECRET_PREFIX));
        }

        if ($type === null || !is_string($encoded)) {
            sodium_memzero($content);
            continue;
        }

        $secret = signerBase64UrlDecode($encoded);
        sodium_memzero($content);
        if (!is_string($secret) || strlen($secret) !== SODIUM_CRYPTO_SIGN_SECRETKEYBYTES) {
            continue;
        }

        try {
            $public = sodium_crypto_sign_publickey_from_secretkey($secret);
            if (!hash_equals($public, substr($secret, -SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES))) {
                continue;
            }

            $keys[] = [
                'type' => $type,
                'file' => $entry,
                'public_key' => signerBase64UrlEncode($public),
                'fingerprint' => substr(hash('sha256', $public), 0, 16),
            ];
        } finally {
            sodium_memzero($secret);
        }
    }

    return $keys;
}

function signerRequireExpectedPublic(array $data, array $key, string $expectedType): string
{
    if ($key['type'] !== $expectedType) {
        sodium_memzero($key['secret']);
        signerFail('Выбран ключ другого типа.', 'wrong_key_type', 403);
    }

    $expected = trim((string) ($data['expected_public_key'] ?? ''));
    $decoded = signerBase64UrlDecode($expected);
    if (!is_string($decoded) || strlen($decoded) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) {
        sodium_memzero($key['secret']);
        signerFail('Некорректный ожидаемый public key.');
    }

    if (!hash_equals($decoded, $key['public'])) {
        sodium_memzero($key['secret']);
        signerFail(
            'Private key не соответствует trust root, выбранному на сайте.',
            'wrong_signing_key',
            403
        );
    }

    $keyId = trim((string) ($data['key_id'] ?? ''));
    $pattern = $expectedType === 'license'
        ? '/^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$/D'
        : '/^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$/D';
    if (preg_match($pattern, $keyId) !== 1) {
        sodium_memzero($key['secret']);
        signerFail('Некорректный key_id.');
    }

    return $keyId;
}

/** @return array<string,mixed> */
function signerLicensePayload(array $data): array
{
    $license = $data['license'] ?? null;
    if (!is_array($license)) {
        signerFail('Отсутствуют параметры лицензии.');
    }

    $installationId = strtolower(trim((string) ($license['installation_id'] ?? '')));
    if (
        preg_match(
            '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/D',
            $installationId
        ) !== 1
    ) {
        signerFail('Некорректный installation_id.');
    }

    $licenseId = trim((string) ($license['license_id'] ?? ''));
    if (preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$/D', $licenseId) !== 1) {
        signerFail('Некорректный license_id.');
    }

    $edition = strtolower(trim((string) ($license['edition'] ?? '')));
    if (preg_match('/^[a-z][a-z0-9._-]{1,63}$/D', $edition) !== 1) {
        signerFail('Некорректный edition.');
    }

    $issuedAt = time();
    $notBefore = $license['not_before'] ?? null;
    $expiresAt = $license['expires_at'] ?? null;
    foreach (['not_before' => $notBefore, 'expires_at' => $expiresAt] as $name => $value) {
        if ($value !== null && (!is_int($value) || $value <= 0)) {
            signerFail("{$name} должен быть Unix timestamp или null.");
        }
    }
    if (is_int($expiresAt) && $expiresAt <= $issuedAt) {
        signerFail('Срок лицензии должен быть позже времени выпуска.');
    }
    if (is_int($notBefore) && is_int($expiresAt) && $notBefore >= $expiresAt) {
        signerFail('Дата начала должна быть раньше даты окончания.');
    }

    $payload = [
        'v' => 1,
        'license_id' => $licenseId,
        'installation_id' => $installationId,
        'issued_at' => $issuedAt,
        'expires_at' => $expiresAt,
        'edition' => $edition,
    ];
    if (is_int($notBefore)) {
        $payload['not_before'] = $notBefore;
    }

    $maxUsers = $license['max_users'] ?? null;
    if ($maxUsers !== null) {
        if (!is_int($maxUsers) || $maxUsers < 1 || $maxUsers > 1000000) {
            signerFail('max_users должен быть от 1 до 1000000.');
        }
        $payload['max_users'] = $maxUsers;
    }

    $customer = trim((string) ($license['customer'] ?? ''));
    if ($customer !== '') {
        $customerLength = function_exists('mb_strlen')
            ? mb_strlen($customer)
            : strlen($customer);
        if ($customerLength > 160) {
            signerFail('Название клиента не должно превышать 160 символов.');
        }
        $payload['customer'] = $customer;
    }

    $features = $license['features'] ?? [];
    if (!is_array($features) || count($features) > 128) {
        signerFail('Некорректный список features.');
    }
    $normalizedFeatures = [];
    foreach ($features as $feature) {
        if (
            !is_string($feature)
            || preg_match('/^[a-z][a-z0-9._-]{1,63}$/D', $feature) !== 1
        ) {
            signerFail('Некорректный feature в лицензии.');
        }
        $normalizedFeatures[$feature] = true;
    }
    if ($normalizedFeatures !== []) {
        $payload['features'] = array_keys($normalizedFeatures);
    }

    return $payload;
}

function signerValidateManifest(string $manifestBytes): void
{
    if ($manifestBytes === '' || strlen($manifestBytes) > MAX_MANIFEST_BYTES) {
        signerFail('Manifest имеет недопустимый размер.');
    }

    try {
        $manifest = json_decode($manifestBytes, true, 32, JSON_THROW_ON_ERROR);
    } catch (JsonException $e) {
        signerFail('Manifest не является корректным JSON.');
    }

    if (
        !is_array($manifest)
        || ($manifest['schema'] ?? null) !== 1
        || ($manifest['product'] ?? null) !== 'workspace-organizer'
        || !is_string($manifest['version'] ?? null)
        || !is_int($manifest['version_code'] ?? null)
        || !in_array($manifest['channel'] ?? null, ['alpha', 'beta', 'stable'], true)
        || !is_string($manifest['source_commit'] ?? null)
        || preg_match('/^[0-9a-f]{40}$/D', $manifest['source_commit']) !== 1
        || !is_int($manifest['min_source_version_code'] ?? null)
        || !is_string($manifest['requires_php'] ?? null)
        || !is_array($manifest['package'] ?? null)
    ) {
        signerFail('Manifest не соответствует Workspace Organizer schema.');
    }

    $package = $manifest['package'];
    if (
        !is_string($package['filename'] ?? null)
        || !str_ends_with($package['filename'], '.zip')
        || !is_string($package['sha256'] ?? null)
        || preg_match('/^[0-9a-f]{64}$/D', $package['sha256']) !== 1
        || !is_int($package['size'] ?? null)
        || $package['size'] < 1
        || ($package['format'] ?? null) !== 'zip'
    ) {
        signerFail('Package metadata в manifest некорректны.');
    }
}

signerRequireRuntime();
signerApplyCors();
signerRequireToken();

$method = strtoupper((string) ($_SERVER['REQUEST_METHOD'] ?? 'GET'));
$path = (string) parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH);

if ($method === 'GET' && $path === '/v1/status') {
    signerRespond([
        'status' => 'ok',
        'api_version' => SIGNER_API_VERSION,
        'php_version' => PHP_VERSION,
        'os_family' => PHP_OS_FAMILY,
        'sodium' => true,
    ]);
}

if ($method === 'POST' && $path === '/v1/select-directory') {
    $directory = signerSelectDirectory();
    signerRespond([
        'status' => 'ok',
        'cancelled' => $directory === null,
        'directory' => $directory,
    ]);
}

if ($method === 'POST' && $path === '/v1/scan') {
    $data = signerJsonBody();
    $directory = (string) ($data['directory'] ?? '');
    signerRespond([
        'status' => 'ok',
        'directory' => signerResolveDirectory($directory),
        'keys' => signerScanDirectory($directory),
    ]);
}

if ($method === 'POST' && $path === '/v1/sign-license') {
    $data = signerJsonBody();
    $directory = (string) ($data['directory'] ?? '');
    $file = (string) ($data['file'] ?? '');
    $key = signerLoadKey($directory, $file);

    $keyId = signerRequireExpectedPublic($data, $key, 'license');
    $payload = signerLicensePayload($data);
    $json = json_encode(
        $payload,
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR
    );
    $payloadEncoded = signerBase64UrlEncode($json);
    $signed = 'wo1.' . $keyId . '.' . $payloadEncoded;
    $signature = sodium_crypto_sign_detached($signed, $key['secret']);
    $token = $signed . '.' . signerBase64UrlEncode($signature);
    $publicEncoded = signerBase64UrlEncode($key['public']);
    sodium_memzero($key['secret']);

    signerRespond([
        'status' => 'ok',
        'token' => $token,
        'key_id' => $keyId,
        'public_key' => $publicEncoded,
        'summary' => [
            'license_id' => $payload['license_id'],
            'installation_id' => $payload['installation_id'],
            'edition' => $payload['edition'],
            'customer' => $payload['customer'] ?? null,
            'expires_at' => $payload['expires_at'],
        ],
    ]);
}

if ($method === 'POST' && $path === '/v1/sign-manifest') {
    $data = signerJsonBody();
    $directory = (string) ($data['directory'] ?? '');
    $file = (string) ($data['file'] ?? '');
    $manifest = $data['manifest'] ?? null;
    if (!is_string($manifest)) {
        signerFail('Manifest должен быть строкой exact bytes.');
    }
    signerValidateManifest($manifest);

    $key = signerLoadKey($directory, $file);
    $keyId = signerRequireExpectedPublic($data, $key, 'update');
    $signature = sodium_crypto_sign_detached(
        UPDATE_SIGNATURE_DOMAIN . $manifest,
        $key['secret']
    );
    $publicEncoded = signerBase64UrlEncode($key['public']);
    sodium_memzero($key['secret']);

    signerRespond([
        'status' => 'ok',
        'signature' => 'wou1.' . $keyId . '.' . signerBase64UrlEncode($signature),
        'key_id' => $keyId,
        'public_key' => $publicEncoded,
    ]);
}

signerFail('Endpoint локального signer не найден.', 'not_found', 404);
