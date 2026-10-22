/** API barrel — import paths stay unchanged (`../api/client`).
 *
 * Split from the monolithic client.ts:
 * - ./http — axios instances + 401/refresh interceptor
 * - ./public — services, appointments, reviews, working-hours, blocked-slots, masters, clients
 * - ./auth — authApi
 * - ./admin — adminApi
 * - ./superadmin — superAdminAuthApi, superAdminApi
 * - ./cabinet — cabinetApi (client self-service)
 */
export { default, refreshClient, assetUrl, API_BASE_URL } from './http';
export * from './public';
export * from './auth';
export * from './admin';
export * from './superadmin';
export * from './cabinet';
export * from './billing';
export * from './support';
