import { Alert, Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as Google from 'expo-auth-session/providers/google';
import { oauthLogin } from './api';
import { saveToken, saveUser } from './auth';
import { GOOGLE_CLIENT_ID, GOOGLE_IOS_CLIENT_ID } from '../config';

WebBrowser.maybeCompleteAuthSession();

export const handleGoogleAuth = async (navigation, onLogin, promptAsync) => {
  try {
    const result = await promptAsync();
    if (result?.type !== 'success') return;

    const { authentication } = result;
    const token = authentication?.accessToken;
    if (!token) {
      Alert.alert('Google Sign In', 'Failed to get access token');
      return;
    }

    const res = await oauthLogin({ provider: 'google', token });
    await saveToken(res.data.token);
    await saveUser(res.data.user);
    onLogin();
  } catch (err) {
    const msg = err.response?.data?.error || 'Google sign in failed';
    Alert.alert('Google Sign In', msg);
  }
};

export const handleAppleAuth = async (navigation, onLogin) => {
  if (Platform.OS !== 'ios') return;

  try {
    const AppleAuthentication = require('expo-apple-authentication');
    const credential = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
    });

    const { identityToken, fullName, email } = credential;
    if (!identityToken) {
      Alert.alert('Apple Sign In', 'Failed to get identity token');
      return;
    }

    const name = fullName
      ? [fullName.givenName, fullName.familyName].filter(Boolean).join(' ')
      : undefined;

    const res = await oauthLogin({
      provider: 'apple',
      token: identityToken,
      ...(name && { name }),
      ...(email && { email }),
    });
    await saveToken(res.data.token);
    await saveUser(res.data.user);
    onLogin();
  } catch (err) {
    if (err.code === 'ERR_REQUEST_CANCELED') return;
    const msg = err.response?.data?.error || 'Apple sign in failed';
    Alert.alert('Apple Sign In', msg);
  }
};
