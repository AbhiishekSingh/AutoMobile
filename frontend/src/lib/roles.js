// Role groups used across the app. Keep in step with SALES_ROLES /
// MANAGER_ROLES in backend app/modules/users/access.py.

// Roles that work leads day to day — they share the same screens
// (Dashboard, Leads, Customers, Follow Ups, Quotations).
export const SALES_ROLES = ['PBA', 'CRE']
export const MANAGER_ROLES = ['OWNER', 'GM', 'ADMIN']

// A CRE covers 1 to this many branches (set by Admin on the Users page).
export const CRE_MAX_BRANCHES = 2

export const isCre = (user) => user?.role === 'CRE'
export const isSales = (user) => SALES_ROLES.includes(user?.role)
