/** API barrel — import paths stay unchanged (`../api/client`).
 *
 * Split from the monolithic client.ts:
 * - ./http — axios instances + 401/refresh interceptor
 * - ./public — services, appointments, reviews, working-hours, blocked-slots, masters, clients
 * - ./auth — authApi
 * - ./admin — adminApi
 * - ./superadmin — superAdminAuthApi, superAdminApi
 */
export { default, refreshClient } from './http'
export * from './public'
export * from './auth'
export * from './admin'
export * from './superadmin'
