const { OAuth2Client } = require('google-auth-library');
const appleSignin = require('apple-signin-auth');

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID;
const APPLE_CLIENT_ID = process.env.APPLE_CLIENT_ID || 'com.haulwallet.app';

const googleClient = new OAuth2Client(GOOGLE_CLIENT_ID);

/**
 * Verify Google ID token and return user payload.
 * @param {string} idToken — token from Google Sign-In on client
 * @returns {{ email: string, name: string, picture: string, sub: string }}
 */
async function verifyGoogleToken(idToken) {
  const ticket = await googleClient.verifyIdToken({
    idToken,
    audience: GOOGLE_CLIENT_ID,
  });
  const payload = ticket.getPayload();
  if (!payload) throw new Error('Empty Google token payload');
  return {
    email: payload.email,
    name: payload.name || null,
    picture: payload.picture || null,
    sub: payload.sub,
  };
}

/**
 * Verify Apple identity token and return user payload.
 * Apple only sends email on the very first sign-in — client must pass it in request body
 * for subsequent logins.
 * @param {string} identityToken — token from Apple Sign-In on client
 * @returns {{ email: string|null, sub: string }}
 */
async function verifyAppleToken(identityToken) {
  const payload = await appleSignin.verifyIdToken(identityToken, {
    audience: APPLE_CLIENT_ID,
    ignoreExpiration: false,
  });
  return {
    email: payload.email || null,
    sub: payload.sub,
  };
}

module.exports = { verifyGoogleToken, verifyAppleToken };
