# Copyright Copyright ClusterHQ Inc.  See LICENSE file for details.

"""
Tests for certification logic in ``flocker.ca._ca``
"""

import datetime
import os

from uuid import uuid4

from Crypto.Util import asn1
from OpenSSL import crypto

from twisted.trial.unittest import SynchronousTestCase
from twisted.python.filepath import FilePath

from .. import (RootCredential, ControlCredential, NodeCredential,
                UserCredential, PathError, EXPIRY_DATE,
                AUTHORITY_CERTIFICATE_FILENAME, AUTHORITY_KEY_FILENAME,
                CONTROL_CERTIFICATE_FILENAME, CONTROL_KEY_FILENAME)

from ...testtools import not_root, skip_on_broken_permissions

NODE_UUID = str(uuid4())


def make_credential_tests(cls, expected_file_name, **kwargs):
    class CredentialTests(SynchronousTestCase):
        """
        Base test case for credential tests.
        """
        def setUp(self):
            self.cert_file_name = expected_file_name + b".crt"
            self.key_file_name = expected_file_name + b".key"
            self.path = FilePath(self.mktemp())
            self.path.makedirs()
            self.ca = RootCredential.initialize(self.path, b"mycluster")
            self.credential = cls.initialize(self.path, self.ca, **kwargs)
            for k, v in kwargs.iteritems():
                setattr(self, k, v)

        def test_certificate_matches_public_key(self):
            """
            A certificate's public key matches the public key it is
            meant to be paired with.
            """
            self.assertTrue(
                self.credential.credential.keypair.keypair.matches(
                    self.credential.credential.certificate.getPublicKey())
            )

        def test_certificate_matches_private_key(self):
            """
            A certificate matches the private key it is meant to
            be paired with.
            """
            priv = self.credential.credential.keypair.keypair.original
            pub = self.credential.credential.certificate
            pub = pub.getPublicKey().original
            pub_asn1 = crypto.dump_privatekey(crypto.FILETYPE_ASN1, pub)
            priv_asn1 = crypto.dump_privatekey(crypto.FILETYPE_ASN1, priv)
            pub_der = asn1.DerSequence()
            pub_der.decode(pub_asn1)
            priv_der = asn1.DerSequence()
            priv_der.decode(priv_asn1)
            pub_modulus = pub_der[1]
            priv_modulus = priv_der[1]
            self.assertEqual(pub_modulus, priv_modulus)

        def test_written_keypair_reloads(self):
            """
            A keypair written by ``UserCredential.initialize`` can be
            successfully reloaded in to an identical ``ControlCertificate``
            instance.
            """
            self.assertEqual(
                self.credential,
                cls.from_path(self.path, **kwargs)
            )

        def test_create_error_on_non_existent_path(self):
            """
            A ``PathError`` is raised if the path given to
            ``UserCredential.initialize`` does not exist.
            """
            path = FilePath(self.mktemp())
            e = self.assertRaises(
                PathError, cls.initialize,
                path, self.ca, **kwargs
            )
            expected = (b"Unable to write certificate file. "
                        b"No such file or directory {path}").format(
                            path=path.child(self.cert_file_name).path)
            self.assertEqual(str(e), expected)

        def test_load_error_on_non_existent_path(self):
            """
            A ``PathError`` is raised if the path given to
            ``UserCredential.from_path`` does not exist.
            """
            path = FilePath(self.mktemp())
            e = self.assertRaises(
                PathError, cls.from_path,
                path, **kwargs
            )
            expected = (b"Certificate file could not be opened. "
                        b"No such file or directory {path}").format(
                            path=path.child(self.cert_file_name).path)
            self.assertEqual(str(e), expected)

        def test_load_error_on_non_existent_certificate_file(self):
            """
            A ``PathError`` is raised if the certificate file path given to
            ``UserCredential.from_path`` does not exist.
            """
            path = FilePath(self.mktemp())
            path.makedirs()
            e = self.assertRaises(
                PathError, cls.from_path,
                path, **kwargs
            )
            expected = ("Certificate file could not be opened. "
                        "No such file or directory "
                        "{path}").format(
                path=path.child(self.cert_file_name).path)
            self.assertEqual(str(e), expected)

        def test_load_error_on_non_existent_key_file(self):
            """
            A ``PathError`` is raised if the key file path given to
            ``UserCredential.from_path`` does not exist.
            """
            path = FilePath(self.mktemp())
            path.makedirs()
            crt_path = path.child(self.cert_file_name)
            crt_file = crt_path.open(b'w')
            crt_file.write(b"dummy")
            crt_file.close()
            e = self.assertRaises(
                PathError, cls.from_path,
                path, **kwargs
            )
            expected = ("Private key file could not be opened. "
                        "No such file or directory "
                        "{path}").format(
                            path=path.child(self.key_file_name).path)
            self.assertEqual(str(e), expected)

        @not_root
        @skip_on_broken_permissions
        def test_load_error_on_unreadable_certificate_file(self):
            """
            A ``PathError`` is raised if the certificate file path given to
            ``UserCredential.from_path`` cannot be opened for reading.
            """
            path = FilePath(self.mktemp())
            path.makedirs()
            crt_path = path.child(self.cert_file_name)
            crt_file = crt_path.open(b'w')
            crt_file.write(b"dummy")
            crt_file.close()
            # make file unreadable
            crt_path.chmod(0o100)
            key_path = path.child(self.key_file_name)
            key_file = key_path.open(b'w')
            key_file.write(b"dummy")
            key_file.close()
            # make file unreadable
            key_path.chmod(0o100)
            e = self.assertRaises(
                PathError, cls.from_path,
                path, **kwargs
            )
            expected = (
                "Certificate file could not be opened. "
                "Permission denied {path}"
            ).format(path=crt_path.path)
            self.assertEqual(str(e), expected)

        @not_root
        @skip_on_broken_permissions
        def test_load_error_on_unreadable_key_file(self):
            """
            A ``PathError`` is raised if the key file path given to
            ``UserCredential.from_path`` cannot be opened for reading.
            """
            path = FilePath(self.mktemp())
            path.makedirs()
            crt_path = path.child(self.cert_file_name)
            crt_file = crt_path.open(b'w')
            crt_file.write(b"dummy")
            crt_file.close()
            key_path = path.child(self.key_file_name)
            key_file = key_path.open(b'w')
            key_file.write(b"dummy")
            key_file.close()
            # make file unreadable
            key_path.chmod(0o100)
            e = self.assertRaises(
                PathError, cls.from_path,
                path, **kwargs
            )
            expected = (
                "Private key file could not be opened. "
                "Permission denied {path}"
            ).format(path=key_path.path)
            self.assertEqual(str(e), expected)

        def test_certificate_ou_matches_ca(self):
            """
            A certificate written by ``UserCredential.initialize`` has the
            issuing authority's common name as its organizational unit name.
            """
            cert = self.credential.credential.certificate.original
            issuer = cert.get_issuer()
            subject = cert.get_subject()
            self.assertEqual(
                issuer.CN,
                subject.OU
            )

        def test_certificate_is_signed_by_ca(self):
            """
            A certificate written by ``UserCredential.initialize`` is signed by
            the certificate authority.
            """
            cert = self.credential.credential.certificate.original
            issuer = cert.get_issuer()
            self.assertEqual(
                issuer.CN,
                self.ca.credential.certificate.getSubject().CN
            )

        def test_certificate_expiration(self):
            """
            A certificate written by ``UserCredential.initialize`` has an
            expiry date 20 years from the date of signing.
            """
            expected_expiry = datetime.datetime.strptime(
                EXPIRY_DATE, "%Y%m%d%H%M%SZ")
            cert = self.credential.credential.certificate.original
            date_str = cert.get_notAfter()
            expiry_date = datetime.datetime.strptime(date_str, "%Y%m%d%H%M%SZ")
            self.assertEqual(expiry_date, expected_expiry)

        def test_certificate_is_rsa_4096_sha_256(self):
            """
            A certificate written by ``UserCredential.initialize`` is an RSA
            4096 bit, SHA-256 format.
            """
            cert = self.credential.credential.certificate.original
            key = self.credential.credential.certificate
            key = key.getPublicKey().original
            self.assertEqual(
                (crypto.TYPE_RSA, 4096, b'sha256WithRSAEncryption'),
                (key.type(), key.bits(), cert.get_signature_algorithm())
            )

        def test_keypair_correct_umask(self):
            """
            A keypair file written by ``NodeCredential.initialize`` has
            the correct permissions (0600).
            """
            key_path = self.path.child(self.key_file_name)
            st = os.stat(key_path.path)
            self.assertEqual(b'0600', oct(st.st_mode & 0777))

        def test_certificate_correct_permission(self):
            """
            A certificate file written by ``NodeCredential.initialize`` has
            the correct access mode set (0600).
            """
            cert_path = self.path.child(self.cert_file_name)
            st = os.stat(cert_path.path)
            self.assertEqual(b'0600', oct(st.st_mode & 0777))

        def test_written_keypair_exists(self):
            """
            ``NodeCredential.initialize`` writes a PEM file to the
            specified path.
            """
            self.assertEqual(
                (True, True),
                (self.path.child(self.cert_file_name).exists(),
                 self.path.child(self.key_file_name).exists())
            )

    return CredentialTests


class UserCredentialTests(
        make_credential_tests(UserCredential, b"alice", username=b"alice")):
    """
    Tests for ``flocker.ca._ca.UserCredential``.
    """
    def test_certificate_subject_username(self):
        """
        A certificate written by ``UserCredential.initialize`` has the
        subject common name "user-{user}" where {user} is the username
        supplied during the certificate's creation.
        """
        cert = self.credential.credential.certificate.original
        subject = cert.get_subject()
        self.assertEqual(subject.CN, b"user-{user}".format(
            user=self.credential.username))


class NodeCredentialTests(
        make_credential_tests(NodeCredential, NODE_UUID, uuid=NODE_UUID)):
    """
    Tests for ``flocker.ca._ca.NodeCredential``.
    """
    def test_certificate_subject_node_uuid(self):
        """
        A certificate written by ``NodeCredential.initialize`` has the
        subject common name "node-{uuid}" where {uuid} is the UUID
        generated during the certificate's creation.
        """
        nc = NodeCredential.initialize(self.path, self.ca)
        cert = nc.credential.certificate.original
        subject = cert.get_subject()
        self.assertEqual(subject.CN, b"node-{uuid}".format(uuid=nc.uuid))


class ControlCredentialTests(SynchronousTestCase):
    """
    Tests for ``flocker.ca._ca.ControlCredential``.
    """
    def setUp(self):
        """
        Generate a RootCredential for the control certificate tests
        to work with.
        """
        self.path = FilePath(self.mktemp())
        self.path.makedirs()
        self.ca = RootCredential.initialize(self.path, b"mycluster")

    def test_written_keypair_exists(self):
        """
        ``ControlCredential.initialize`` writes a PEM file to the
        specified path.
        """
        ControlCredential.initialize(self.path, self.ca)
        self.assertEqual(
            (True, True),
            (self.path.child(AUTHORITY_CERTIFICATE_FILENAME).exists(),
             self.path.child(AUTHORITY_KEY_FILENAME).exists())
        )

    def test_certificate_matches_public_key(self):
        """
        A certificate's public key matches the public key it is
        meant to be paired with.
        """
        cc = ControlCredential.initialize(self.path, self.ca)
        self.assertTrue(
            cc.credential.keypair.keypair.matches(
                cc.credential.certificate.getPublicKey())
        )

    def test_certificate_matches_private_key(self):
        """
        A certificate matches the private key it is meant to
        be paired with.
        """
        cc = ControlCredential.initialize(self.path, self.ca)
        priv = cc.credential.keypair.keypair.original
        pub = cc.credential.certificate.getPublicKey().original
        pub_asn1 = crypto.dump_privatekey(crypto.FILETYPE_ASN1, pub)
        priv_asn1 = crypto.dump_privatekey(crypto.FILETYPE_ASN1, priv)
        pub_der = asn1.DerSequence()
        pub_der.decode(pub_asn1)
        priv_der = asn1.DerSequence()
        priv_der.decode(priv_asn1)
        pub_modulus = pub_der[1]
        priv_modulus = priv_der[1]
        self.assertEqual(pub_modulus, priv_modulus)

    def test_written_keypair_reloads(self):
        """
        A keypair written by ``ControlCredential.initialize`` can be
        successfully reloaded in to an identical ``ControlCredential``
        instance.
        """
        cc1 = ControlCredential.initialize(self.path, self.ca)
        cc2 = ControlCredential.from_path(self.path)
        self.assertEqual(cc1, cc2)

    def test_keypair_correct_umask(self):
        """
        A keypair file written by ``ControlCredential.initialize`` has
        the correct permissions (0600).
        """
        ControlCredential.initialize(self.path, self.ca)
        keyPath = self.path.child(CONTROL_KEY_FILENAME)
        st = os.stat(keyPath.path)
        self.assertEqual(b'0600', oct(st.st_mode & 0777))

    def test_certificate_correct_permission(self):
        """
        A certificate file written by ``ControlCredential.initialize`` has
        the correct access mode set (0600).
        """
        ControlCredential.initialize(self.path, self.ca)
        keyPath = self.path.child(CONTROL_CERTIFICATE_FILENAME)
        st = os.stat(keyPath.path)
        self.assertEqual(b'0600', oct(st.st_mode & 0777))

    def test_create_error_on_non_existent_path(self):
        """
        A ``PathError`` is raised if the path given to
        ``ControlCredential.initialize`` does not exist.
        """
        path = FilePath(self.mktemp())
        e = self.assertRaises(
            PathError, ControlCredential.initialize, path, self.ca
        )
        expected = ("Unable to write certificate file. "
                    "No such file or directory {path}").format(
                        path=path.child(CONTROL_CERTIFICATE_FILENAME).path)
        self.assertEqual(str(e), expected)

    def test_load_error_on_non_existent_path(self):
        """
        A ``PathError`` is raised if the path given to
        ``ControlCredential.from_path`` does not exist.
        """
        path = FilePath(self.mktemp())
        e = self.assertRaises(
            PathError, ControlCredential.from_path, path
        )
        expected = ("Certificate file could not be opened. "
                    "No such file or directory {path}").format(
                        path=path.child(CONTROL_CERTIFICATE_FILENAME).path)
        self.assertEqual(str(e), expected)

    def test_load_error_on_non_existent_certificate_file(self):
        """
        A ``PathError`` is raised if the certificate file path given to
        ``ControlCredential.from_path`` does not exist.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        e = self.assertRaises(
            PathError, ControlCredential.from_path, path
        )
        expected = ("Certificate file could not be opened. "
                    "No such file or directory "
                    "{path}").format(
                        path=path.child(CONTROL_CERTIFICATE_FILENAME).path)
        self.assertEqual(str(e), expected)

    def test_load_error_on_non_existent_key_file(self):
        """
        A ``PathError`` is raised if the key file path given to
        ``ControlCredential.from_path`` does not exist.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        crt_path = path.child(CONTROL_CERTIFICATE_FILENAME)
        crt_file = crt_path.open(b'w')
        crt_file.write(b"dummy")
        crt_file.close()
        e = self.assertRaises(
            PathError, ControlCredential.from_path, path
        )
        expected = ("Private key file could not be opened. "
                    "No such file or directory "
                    "{path}").format(
                        path=path.child(CONTROL_KEY_FILENAME).path)
        self.assertEqual(str(e), expected)

    @not_root
    @skip_on_broken_permissions
    def test_load_error_on_unreadable_certificate_file(self):
        """
        A ``PathError`` is raised if the certificate file path given to
        ``ControlCredential.from_path`` cannot be opened for reading.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        crt_path = path.child(CONTROL_CERTIFICATE_FILENAME)
        crt_file = crt_path.open(b'w')
        crt_file.write(b"dummy")
        crt_file.close()
        # make file unreadable
        crt_path.chmod(0o100)
        key_path = path.child(CONTROL_KEY_FILENAME)
        key_file = key_path.open(b'w')
        key_file.write(b"dummy")
        key_file.close()
        # make file unreadable
        key_path.chmod(0o100)
        e = self.assertRaises(
            PathError, ControlCredential.from_path, path
        )
        expected = (
            "Certificate file could not be opened. "
            "Permission denied {path}"
        ).format(path=crt_path.path)
        self.assertEqual(str(e), expected)

    @not_root
    @skip_on_broken_permissions
    def test_load_error_on_unreadable_key_file(self):
        """
        A ``PathError`` is raised if the key file path given to
        ``ControlCredential.from_path`` cannot be opened for reading.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        crt_path = path.child(CONTROL_CERTIFICATE_FILENAME)
        crt_file = crt_path.open(b'w')
        crt_file.write(b"dummy")
        crt_file.close()
        key_path = path.child(CONTROL_KEY_FILENAME)
        key_file = key_path.open(b'w')
        key_file.write(b"dummy")
        key_file.close()
        # make file unreadable
        key_path.chmod(0o100)
        e = self.assertRaises(
            PathError, ControlCredential.from_path, path
        )
        expected = (
            "Private key file could not be opened. "
            "Permission denied {path}"
        ).format(path=key_path.path)
        self.assertEqual(str(e), expected)

    def test_certificate_subject_control_service(self):
        """
        A certificate written by ``ControlCredential.initialize`` has the
        subject common name "control-service"
        """
        cc = ControlCredential.initialize(self.path, self.ca)
        cert = cc.credential.certificate.original
        subject = cert.get_subject()
        self.assertEqual(subject.CN, b"control-service")

    def test_certificate_ou_matches_ca(self):
        """
        A certificate written by ``ControlCredential.initialize`` has the
        issuing authority's common name as its organizational unit name.
        """
        cc = ControlCredential.initialize(self.path, self.ca)
        cert = cc.credential.certificate.original
        issuer = cert.get_issuer()
        subject = cert.get_subject()
        self.assertEqual(
            issuer.CN,
            subject.OU
        )

    def test_certificate_is_signed_by_ca(self):
        """
        A certificate written by ``ControlCredential.initialize`` is signed by
        the certificate authority.
        """
        cc = ControlCredential.initialize(self.path, self.ca)
        cert = cc.credential.certificate.original
        issuer = cert.get_issuer()
        self.assertEqual(
            issuer.CN,
            self.ca.credential.certificate.getSubject().CN
        )

    def test_certificate_expiration(self):
        """
        A certificate written by ``ControlCredential.initialize`` has an expiry
        date 20 years from the date of signing.

        XXX: This test is prone to intermittent failure depending on the time
        of day it is run. Fixed in
        https://github.com/ClusterHQ/flocker/pull/1339
        """
        expected_expiry = datetime.datetime.strptime(
            EXPIRY_DATE, "%Y%m%d%H%M%SZ")
        cc = ControlCredential.initialize(self.path, self.ca)
        cert = cc.credential.certificate.original
        date_str = cert.get_notAfter()
        expiry_date = datetime.datetime.strptime(date_str, "%Y%m%d%H%M%SZ")
        self.assertEqual(expiry_date, expected_expiry)

    def test_certificate_is_rsa_4096_sha_256(self):
        """
        A certificate written by ``ControlCredential.initialize`` is an RSA
        4096 bit, SHA-256 format.
        """
        cc = ControlCredential.initialize(self.path, self.ca)
        cert = cc.credential.certificate.original
        key = cc.credential.certificate.getPublicKey().original
        self.assertEqual(
            (crypto.TYPE_RSA, 4096, b'sha256WithRSAEncryption'),
            (key.type(), key.bits(), cert.get_signature_algorithm())
        )


class RootCredentialTests(SynchronousTestCase):
    """
    Tests for ``flocker.ca._ca.RootCredential``.
    """
    def test_written_keypair_exists(self):
        """
        ``RootCredential.initialize`` writes a PEM file to the
        specified path.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        RootCredential.initialize(path, b"mycluster")
        self.assertEqual(
            (True, True),
            (path.child(AUTHORITY_CERTIFICATE_FILENAME).exists(),
             path.child(AUTHORITY_KEY_FILENAME).exists())
        )

    def test_certificate_matches_public_key(self):
        """
        A certificate's public key matches the public key it is
        meant to be paired with.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        ca = RootCredential.initialize(path, b"mycluster")
        self.assertTrue(
            ca.credential.keypair.keypair.matches(
                ca.credential.certificate.getPublicKey())
        )

    def test_certificate_matches_private_key(self):
        """
        A certificate matches the private key it is meant to
        be paired with.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        ca = RootCredential.initialize(path, b"mycluster")
        priv = ca.credential.keypair.keypair.original
        pub = ca.credential.certificate.getPublicKey().original
        pub_asn1 = crypto.dump_privatekey(crypto.FILETYPE_ASN1, pub)
        priv_asn1 = crypto.dump_privatekey(crypto.FILETYPE_ASN1, priv)
        pub_der = asn1.DerSequence()
        pub_der.decode(pub_asn1)
        priv_der = asn1.DerSequence()
        priv_der.decode(priv_asn1)
        pub_modulus = pub_der[1]
        priv_modulus = priv_der[1]
        self.assertEqual(pub_modulus, priv_modulus)

    def test_written_keypair_reloads(self):
        """
        A keypair written by ``RootCredential.initialize`` can be
        successfully reloaded in to an identical ``RootCredential``
        instance.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        ca1 = RootCredential.initialize(path, b"mycluster")
        ca2 = RootCredential.from_path(path)
        self.assertEqual(ca1, ca2)

    def test_keypair_correct_umask(self):
        """
        A keypair file written by ``RootCredential.initialize`` has
        the correct permissions (0600).
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        RootCredential.initialize(path, b"mycluster")
        keyPath = path.child(AUTHORITY_KEY_FILENAME)
        st = os.stat(keyPath.path)
        self.assertEqual(b'0600', oct(st.st_mode & 0777))

    def test_certificate_correct_permission(self):
        """
        A certificate file written by ``RootCredential.initialize`` has
        the correct access mode set (0600).
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        RootCredential.initialize(path, b"mycluster")
        keyPath = path.child(AUTHORITY_CERTIFICATE_FILENAME)
        st = os.stat(keyPath.path)
        self.assertEqual(b'0600', oct(st.st_mode & 0777))

    def test_create_error_on_non_existent_path(self):
        """
        A ``PathError`` is raised if the path given to
        ``RootCredential.initialize`` does not exist.
        """
        path = FilePath(self.mktemp())
        e = self.assertRaises(
            PathError, RootCredential.initialize, path, b"mycluster"
        )
        expected = ("Unable to write certificate file. "
                    "No such file or directory "
                    "{path}").format(path=path.child(
                        AUTHORITY_CERTIFICATE_FILENAME).path)
        self.assertEqual(str(e), expected)

    def test_load_error_on_non_existent_path(self):
        """
        A ``PathError`` is raised if the path given to
        ``RootCredential.from_path`` does not exist.
        """
        path = FilePath(self.mktemp())
        e = self.assertRaises(
            PathError, RootCredential.from_path, path
        )
        expected = (
            "Unable to load certificate authority file. Please run "
            "`flocker-ca initialize` to generate a new certificate "
            "authority. No such file or directory {path}"
        ).format(path=path.child(AUTHORITY_CERTIFICATE_FILENAME).path)
        self.assertEqual(str(e), expected)

    def test_load_error_on_non_existent_certificate_file(self):
        """
        A ``PathError`` is raised if the certificate file path given to
        ``RootCredential.from_path`` does not exist.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        e = self.assertRaises(
            PathError, RootCredential.from_path, path
        )
        expected = (
            "Unable to load certificate authority file. Please run "
            "`flocker-ca initialize` to generate a new certificate "
            "authority. No such file or directory {path}"
        ).format(path=path.child(AUTHORITY_CERTIFICATE_FILENAME).path)
        self.assertEqual(str(e), expected)

    def test_load_error_on_non_existent_key_file(self):
        """
        A ``PathError`` is raised if the key file path given to
        ``RootCredential.from_path`` does not exist.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        crt_path = path.child(AUTHORITY_CERTIFICATE_FILENAME)
        crt_file = crt_path.open(b'w')
        crt_file.write(b"dummy")
        crt_file.close()
        e = self.assertRaises(
            PathError, RootCredential.from_path, path
        )
        expected = (
            "Unable to load certificate authority file. Please run "
            "`flocker-ca initialize` to generate a new certificate "
            "authority. No such file or directory {path}"
        ).format(path=path.child(AUTHORITY_KEY_FILENAME).path)
        self.assertEqual(str(e), expected)

    @not_root
    @skip_on_broken_permissions
    def test_load_error_on_unreadable_certificate_file(self):
        """
        A ``PathError`` is raised if the certificate file path given to
        ``RootCredential.from_path`` cannot be opened for reading.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        crt_path = path.child(AUTHORITY_CERTIFICATE_FILENAME)
        crt_file = crt_path.open(b'w')
        crt_file.write(b"dummy")
        crt_file.close()
        # make file unreadable
        crt_path.chmod(0o100)
        key_path = path.child(AUTHORITY_KEY_FILENAME)
        key_file = key_path.open(b'w')
        key_file.write(b"dummy")
        key_file.close()
        # make file unreadable
        key_path.chmod(0o100)
        e = self.assertRaises(
            PathError, RootCredential.from_path, path
        )
        expected = (
            "Unable to load certificate authority file. "
            "Permission denied {path}"
        ).format(path=crt_path.path)
        self.assertEqual(str(e), expected)

    @not_root
    @skip_on_broken_permissions
    def test_load_error_on_unreadable_key_file(self):
        """
        A ``PathError`` is raised if the key file path given to
        ``RootCredential.from_path`` cannot be opened for reading.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        crt_path = path.child(AUTHORITY_CERTIFICATE_FILENAME)
        crt_file = crt_path.open(b'w')
        crt_file.write(b"dummy")
        crt_file.close()
        key_path = path.child(AUTHORITY_KEY_FILENAME)
        key_file = key_path.open(b'w')
        key_file.write(b"dummy")
        key_file.close()
        # make file unreadable
        key_path.chmod(0o100)
        e = self.assertRaises(
            PathError, RootCredential.from_path, path
        )
        expected = (
            "Unable to load certificate authority file. "
            "Permission denied {path}"
        ).format(path=key_path.path)
        self.assertEqual(str(e), expected)

    def test_certificate_is_self_signed(self):
        """
        A certificate written by ``RootCredential.initialize`` is a
        self-signed certificate.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        ca = RootCredential.initialize(path, b"mycluster")
        cert = ca.credential.certificate.original
        issuer = cert.get_issuer().get_components()
        subject = cert.get_subject().get_components()
        self.assertEqual(issuer, subject)

    def test_certificate_expiration(self):
        """
        A certificate written by ``RootCredential.initialize`` has an expiry
        date 20 years from the date of signing.

        XXX: This test is prone to intermittent failure depending on the time
        of day it is run. Fixed in
        https://github.com/ClusterHQ/flocker/pull/1339
        """
        expected_expiry = datetime.datetime.strptime(
            EXPIRY_DATE, "%Y%m%d%H%M%SZ")
        path = FilePath(self.mktemp())
        path.makedirs()
        ca = RootCredential.initialize(path, b"mycluster")
        cert = ca.credential.certificate.original
        date_str = cert.get_notAfter()
        expiry_date = datetime.datetime.strptime(date_str, "%Y%m%d%H%M%SZ")
        self.assertEqual(expiry_date, expected_expiry)

    def test_certificate_is_rsa_4096_sha_256(self):
        """
        A certificate written by ``RootCredential.initialize`` is an RSA
        4096 bit, SHA-256 format.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        ca = RootCredential.initialize(path, b"mycluster")
        cert = ca.credential.certificate.original
        key = ca.credential.certificate.getPublicKey().original
        self.assertEqual(
            (crypto.TYPE_RSA, 4096, b'sha256WithRSAEncryption'),
            (key.type(), key.bits(), cert.get_signature_algorithm())
        )
