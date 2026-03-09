export type Role = 'user' | 'admin' | 'management'

export interface User {
  id: string
  name: string
  email: string
  role: Role
  org_id?: string | null
}

export type Permission =
  | 'domains:view'
  | 'generate:run'
  | 'generate:download'
  | 'compliance:view'
  | 'compliance:run'
  | 'compliance:export'
  | 'analytics:view'
  | 'analytics:generate'
  | 'bss:upload_schema'
  | 'mock:generate'
  | 'users:manage'
  | 'audit:view'
  | 'settings:manage'
  | 'orgs:view'
  | 'orgs:manage'

export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  user: [
    'domains:view',
    'generate:run',
    'generate:download',
    'compliance:view',
    'analytics:view',
    'analytics:generate',
  ],
  admin: [
    'domains:view',
    'generate:run',
    'generate:download',
    'compliance:view',
    'compliance:run',
    'compliance:export',
    'analytics:view',
    'analytics:generate',
    'bss:upload_schema',
    'mock:generate',
    'audit:view',
    'settings:manage',
    'orgs:view',
  ],
  management: [
    'domains:view',
    'generate:run',
    'generate:download',
    'compliance:view',
    'compliance:run',
    'compliance:export',
    'analytics:view',
    'analytics:generate',
    'bss:upload_schema',
    'mock:generate',
    'users:manage',
    'audit:view',
    'settings:manage',
    'orgs:view',
    'orgs:manage',
  ],
}

export const ROLE_LABELS: Record<Role, string> = {
  user: 'User',
  admin: 'Admin',
  management: 'Management',
}

export const DEMO_USERS: User[] = [
  { id: '1', name: 'Alex Analyst', email: 'alex@telco.com', role: 'user', org_id: 'org-demo' },
  { id: '2', name: 'Sarah Admin', email: 'sarah@telco.com', role: 'admin', org_id: 'org-demo' },
  { id: '3', name: 'Mike Director', email: 'mike@telco.com', role: 'management', org_id: 'org-demo' },
]
