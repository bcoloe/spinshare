"""Unit tests of the security utilities."""

import datetime

import pytest
from app.utils import security


class TestSecurity:
    def test_hash_password(self):
        """Test that hashing does in fact result in a different password"""
        test_password = "a-FINE-password123!"
        assert security.hash_password(test_password) != test_password

    def test_password_verify(self):
        """Test that password verification works"""
        password = "a-FINE-password123!"
        hashed_password = security.hash_password(password)

        assert security.verify_password(password, hashed_password)
        assert not security.verify_password(password.upper(), hashed_password)

    @pytest.mark.parametrize(
        "password,expect_valid,expect_reasons",
        [
            # test valid
            ("a-FINE-password123!", True, []),
            # test too short
            ("1tooS!", False, [security.PasswordStrengthConditions.Length]),
            # test too long
            ("a-FINE-password123!" * 100, False, [security.PasswordStrengthConditions.Length]),
            # test missing uppercase
            ("a-fine-password123!", False, [security.PasswordStrengthConditions.UppercaseLetter]),
            # test missing lowercase
            (
                "a-fine-password123!".upper(),
                False,
                [security.PasswordStrengthConditions.LowercaseLetter],
            ),
            # test missing numbers
            ("a-FINE-password!", False, [security.PasswordStrengthConditions.Number]),
            # test spaces
            ("a FINE password123!", False, [security.PasswordStrengthConditions.NoSpaces]),
            # test no special characters
            ("a-FINE-password123", False, [security.PasswordStrengthConditions.SpecialCharacters]),
            # test multiple violations
            (
                "a-FINE password",
                False,
                [
                    security.PasswordStrengthConditions.SpecialCharacters,
                    security.PasswordStrengthConditions.Number,
                    security.PasswordStrengthConditions.NoSpaces,
                ],
            ),
        ],
    )
    def test_validate_password_strength(
        self, password, expect_valid, expect_reasons: list[security.PasswordStrengthConditions]
    ):
        is_valid, reasons = security.validate_password_strength(password)

        assert is_valid == expect_valid
        assert len(reasons) == len(expect_reasons)
        if expect_reasons:
            expected_reasons_set = {x.value.reason for x in expect_reasons}
            reasons_set = set(reasons)

            assert reasons_set == expected_reasons_set

    def test_create_and_decode_access_token_default(self, mocker, fake_now):
        """Test that encoding and decoding is consistent for default access tokens"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_access_token(data)

        decoded_data = security.decode_access_token(encoded_token, verify_exp=False)
        for k, v in data.items():
            assert k in decoded_data
            assert decoded_data[k] == v
        assert decoded_data.get("type") == "access"
        assert datetime.datetime.fromtimestamp(decoded_data.get("iat"), datetime.UTC) == fake_now
        expected_expiration = fake_now + datetime.timedelta(
            minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        assert (
            datetime.datetime.fromtimestamp(decoded_data.get("exp"), datetime.UTC)
            == expected_expiration
        )

    def test_create_and_decode_access_token_custom(self, mocker, fake_now):
        """Test that encoding and decoding is consistent for access tokens with custom expiration"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        expiration_delta = datetime.timedelta(days=3)
        expected_expiration = fake_now + expiration_delta

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_access_token(data, expiration_delta)

        decoded_data = security.decode_access_token(encoded_token, verify_exp=False)
        for k, v in data.items():
            assert k in decoded_data
            assert decoded_data[k] == v
        assert decoded_data.get("type") == "access"
        assert datetime.datetime.fromtimestamp(decoded_data.get("iat"), datetime.UTC) == fake_now
        assert (
            datetime.datetime.fromtimestamp(decoded_data.get("exp"), datetime.UTC)
            == expected_expiration
        )

    def test_create_and_decode_access_token_expired(self, mocker, fake_now):
        """Test that decoding expired access token results in None"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_access_token(data)

        assert security.decode_access_token(encoded_token, verify_exp=True) is None

    def test_decode_access_token_rejects_refresh(self, mocker, fake_now):
        """Test that attempting to decode a non-access token is rejected"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_refresh_token(data)

        assert security.decode_access_token(encoded_token, verify_exp=False) is None

    def test_create_and_decode_refresh_token_default(self, mocker, fake_now):
        """Test that encoding and decoding is consistent for default refresh tokens"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_refresh_token(data)

        decoded_data = security.decode_refresh_token(encoded_token, verify_exp=False)
        for k, v in data.items():
            assert k in decoded_data
            assert decoded_data[k] == v
        assert decoded_data.get("type") == "refresh"
        assert datetime.datetime.fromtimestamp(decoded_data.get("iat"), datetime.UTC) == fake_now
        expected_expiration = fake_now + datetime.timedelta(days=security.REFRESH_TOKEN_EXPIRE_DAYS)
        assert (
            datetime.datetime.fromtimestamp(decoded_data.get("exp"), datetime.UTC)
            == expected_expiration
        )

    def test_create_and_decode_refresh_token_custom(self, mocker, fake_now):
        """Test that encoding and decoding is consistent for refresh tokens with custom expiration"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        expiration_delta = datetime.timedelta(days=30)
        expected_expiration = fake_now + expiration_delta

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_refresh_token(data, expiration_delta)

        decoded_data = security.decode_refresh_token(encoded_token, verify_exp=False)
        for k, v in data.items():
            assert k in decoded_data
            assert decoded_data[k] == v
        assert decoded_data.get("type") == "refresh"
        assert datetime.datetime.fromtimestamp(decoded_data.get("iat"), datetime.UTC) == fake_now
        assert (
            datetime.datetime.fromtimestamp(decoded_data.get("exp"), datetime.UTC)
            == expected_expiration
        )

    def test_create_and_decode_refresh_token_expired(self, mocker, fake_now):
        """Test that decoding expired refresh token results in None"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_refresh_token(data)

        assert security.decode_refresh_token(encoded_token, verify_exp=True) is None

    def test_decode_refresh_token_rejects_access(self, mocker, fake_now):
        """Test that attempting to decode a non-access token is rejected"""
        mocker.patch("app.utils.security.datetime", now=lambda _: fake_now)

        data = {"sub": "1", "email": "user@test.com"}
        encoded_token = security.create_access_token(data)

        assert security.decode_refresh_token(encoded_token, verify_exp=False) is None
