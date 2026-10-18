/**
 * PKCE (Proof Key for Code Exchange) helpers for VK ID OAuth.
 *
 * VK mandates PKCE: the browser generates a random `code_verifier`, sends
 * only its SHA-256 (`code_challenge`) to the authorize endpoint, and must
 * present the original verifier when the code is exchanged for tokens. A
 * leaked authorization code is then useless without the verifier.
 */

/** Random, URL-safe verifier (43–128 chars per RFC 7636). */
export function generateCodeVerifier(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

/** BASE64URL(SHA256(verifier)) — the value sent to VK in the redirect. */
export async function generateCodeChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64UrlEncode(new Uint8Array(digest));
}

/** base64url without padding (RFC 7636 §4.2). */
function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
