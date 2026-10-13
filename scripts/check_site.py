"""Check the public website, downloads and signed update feeds before Pages deployment."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

BASE_URL = 'https://dogd485.github.io/'
PUBLIC_KEY = 'MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAu5UEs3D7N56OxVLXLHLUYqAxovN/AcBNStbTtrGZg3FJkGkqY2XbK1JBnU9z4UuaUi5k6hPIoKihoRxNzNAdaizLwub4giapoPNcf/M8q9G52h1/+2HyZbGsK8TZpEyvhg6E5GhC3GbAgmtwTW0YDZFF+43BmgypieKKHDE7aKPl+wq22V+1JHrzI8jaRmiOwyhTQ3ZJTqo0tEl2HRZSvtSmJ4p3aAFwdCBYgGibikfcwAoKCMtz2bvJ6fPv/PNLxEXLpwbmin5OOmuRGqJyIPGSQyXrelFz4wuqrHsYNcjVvczxlxOteTVmkWR2HbmyQZC8akMpomqjGqpbOed1e4TQolZjU18ZtnxDgfOmr84KA/0OUW/fvhJq5L9EJF1NanfRRXlCw1l/zAZ7sXIecQlPEIxi9ivenWDY+pA+DDx3OP7dmdYlhNJ2qnrU0i/ZWIp33Xnw4QSLBZ0aeoRFrHNQmjCz1jr5GGyHNSsHOPcjCVqSsGv3B4VeymQIGOMXAgMBAAE='
CERTIFICATE = '8fc45e48e4fe6af28aca5989ee19072a98fa6859498182e62e6c471638ca5858'
STATIC_FILES = {
    '.nojekyll', 'index.html', 'privacy.html', 'licenses.html', 'release-notes.html',
    'releases.json', 'robots.txt', 'assets/site.js', 'assets/site.css', 'assets/mark.svg',
    'licenses/third-party-notices.txt', 'licenses/tailnet-notices.txt', 'licenses/overdrive-notice.txt',
    'updates/vehicle-public.json', 'updates/phone-public.json',
}
REPOSITORY_FILES = {'README.md', '.github/workflows/pages.yml', 'scripts/check_site.py'}

# Keep earlier published downloads for direct links and cached signed feeds.
ARCHIVED_DOWNLOADS = {
    'downloads/SealionHome-0.9.60-vehicle-release.apk':
        (33374505, '5bacb9aebfeac6416cb821c552dfe825bb5e63213af6517725d392f66f0a5e98'),
    'downloads/SealionLink-0.8.39-phone-release.apk':
        (24385104, '6c98f25284bdfd739d692e1ffd159043d20f0f73504feadf58fe9f1e65f7c08c'),

    'downloads/SealionLink-0.8.38-phone-release.apk':
        (24385104, '6a4fd89ab7bff52f4d3875a0a12514f79bf0e502caf40105791e3904dc0a9efd'),
    'downloads/SealionHome-0.9.59-vehicle-release.apk':
        (33358121, '9d19c58d59079de5892495a98624e3008237199788b1868eb54c0095e9c944bf'),
    'downloads/SealionHome-0.9.58-vehicle-release.apk':
        (33358121, '8da1e4fcbd799bfff4b5372d3fabc96881966503b09724d0118c91237c897895'),
    'downloads/SealionLink-0.8.37-phone-release.apk':
        (24385104, '8968d4549408bb776b1837c9fd20ce5373f8717fc0368f8a7010de317870a271'),
    'downloads/SealionHome-0.9.57-vehicle-release.apk':
        (33341737, '8f72ede9330c2d69b85e23693b850cfd399591f38ed4c1cb940892ffaa05c6ec'),
    'downloads/SealionHome-0.9.56-vehicle-release.apk':
        (33325353, '6cd865e1ebc7d81d10b5f3d12078d5485a2d596f5d9bb0198924bb9e83f4830e'),
}



def require(value, message):
    if not value:
        raise ValueError(message)


def valid_notes(notes):
    if not isinstance(notes, list) or not 0 < len(notes) <= 20:
        return False
    try:
        return all(isinstance(note, str) and note and '\0' not in note
                   and len(note.encode('utf-16-le')) // 2 <= 500 for note in notes)
    except UnicodeEncodeError:
        return False


def files(directory, ignore_git=False):
    require(directory.is_dir() and not directory.is_symlink(), 'Expected a real directory')
    found = {}
    for path in directory.rglob('*'):
        relative = path.relative_to(directory).as_posix()
        if ignore_git and (relative == '.git' or relative.startswith('.git/')):
            continue
        require(not path.is_symlink(), 'Symbolic links cannot be published')
        if path.is_file():
            require(path.stat().st_nlink == 1, 'Hard links cannot be published')
            found[relative] = path
    return found


def verify_signature(raw, signature):
    der = base64.b64decode(PUBLIC_KEY, validate=True)
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError:
        executable = shutil.which('openssl')
        require(executable, 'OpenSSL is required to verify signed update feeds')
        encoded = base64.b64encode(der).decode('ascii')
        pem = '-----BEGIN PUBLIC KEY-----\n' + '\n'.join(encoded[i:i+64] for i in range(0, len(encoded), 64)) + '\n-----END PUBLIC KEY-----\n'
        with tempfile.TemporaryDirectory(prefix='sealion-feed-check-') as temporary:
            temporary = Path(temporary)
            (temporary / 'public.pem').write_text(pem, encoding='ascii')
            (temporary / 'payload').write_bytes(raw)
            (temporary / 'signature').write_bytes(signature)
            result = subprocess.run([executable, 'dgst', '-sha256', '-verify', str(temporary / 'public.pem'),
                                     '-signature', str(temporary / 'signature'), str(temporary / 'payload')],
                                    capture_output=True)
            require(result.returncode == 0, 'Update feed signature is invalid')
    else:
        key = serialization.load_der_public_key(der)
        require(isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048, 'Invalid pinned update public key')
        key.verify(signature, raw, padding.PKCS1v15(), hashes.SHA256())


def check(site, repository=None):
    require(BASE_URL.startswith('https://') and BASE_URL.endswith('/') and '__' not in BASE_URL,
            'Publication URL has not been configured')
    inventory = files(site)
    require(STATIC_FILES <= inventory.keys(), 'A required public website file is missing')
    releases = json.loads(inventory['releases.json'].read_text(encoding='utf-8'))
    require(releases.get('schema') == 1 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', releases.get('date', '')),
            'Invalid public release metadata')
    allowed = set(STATIC_FILES)
    for kind, product, package in [('vehicle', 'SealionHome', 'kr.personal.sealion.home.release'),
                                   ('phone', 'SealionLink', 'kr.personal.sealion.link.release')]:
        value = releases.get(kind)
        require(isinstance(value, dict), 'Both public downloads must be ready before publication')
        version = value.get('versionName')
        require(isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version), 'Invalid public version')
        filename = 'downloads/' + product + '-' + version + '-' + kind + '-release.apk'
        require(value.get('file') == filename and filename in inventory, 'Public APK path mismatch')
        require(type(value.get('versionCode')) is int and value['versionCode'] > 0, 'Invalid public version code')
        require(type(value.get('bytes')) is int and 0 < value['bytes'] < 100 * 1024 * 1024,
                'APK must fit the repository file limit')
        require(re.fullmatch(r'[0-9a-f]{64}', value.get('sha256', '')), 'Invalid public APK hash')
        path = inventory[filename]
        require(path.stat().st_size == value['bytes'], 'Public APK size mismatch')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(digest == value['sha256'], 'Public APK hash mismatch')
        feed = inventory['updates/' + kind + '-public.json'].read_bytes()
        require(0 < len(feed) <= 131072, 'Signed feed exceeds the app reader size bound')
        envelope = json.loads(feed)
        require(set(envelope) == {'payload', 'signature'}, 'Unexpected signed feed fields')
        raw = base64.b64decode(envelope['payload'], validate=True)
        signature = base64.b64decode(envelope['signature'], validate=True)
        require(0 < len(raw) <= 65536 and 0 < len(signature) <= 1024, 'Signed feed exceeds its size bound')
        verify_signature(raw, signature)
        payload = json.loads(raw)
        require(type(payload.get('minSdk')) is int and 28 <= payload['minSdk'] <= 34,
                'Invalid signed minimum Android SDK')
        expected = {'schema': 1, 'app': kind, 'channel': 'public', 'package': package,
                    'versionCode': value['versionCode'], 'versionName': version,
                    'apkUrl': BASE_URL + filename, 'apkBytes': value['bytes'], 'sha256': digest,
                    'certificateSha256': [CERTIFICATE]}
        require(all(payload.get(key) == expected_value for key, expected_value in expected.items()),
                'Signed feed differs from the public APK or install identity')
        require(valid_notes(payload.get('changelog')), 'Invalid public release notes')
        allowed.add(filename)
    for name, (size, digest) in ARCHIVED_DOWNLOADS.items():
        if name in inventory:
            path = inventory[name]
            require(path.stat().st_size == size and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                    'Archived public APK differs from its previously verified release')
            allowed.add(name)
    require(set(inventory) == allowed, 'Unexpected files in public website output')
    if repository is not None:
        root_files = files(repository, ignore_git=True)
        expected_files = REPOSITORY_FILES | {'site/' + name for name in allowed}
        require(set(root_files) == expected_files, 'Repository contains files outside the public website allowlist')
    return len(allowed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--repository', type=Path)
    args = parser.parse_args()
    count = check(args.site.resolve(), args.repository.resolve() if args.repository else None)
    print('Public website verified: ' + str(count) + ' files; two signed feeds and matching APKs.')


if __name__ == '__main__':
    main()
