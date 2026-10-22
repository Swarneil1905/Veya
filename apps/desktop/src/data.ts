export type RunStatus = 'Review' | 'Completed' | 'Running' | 'Failed' | 'Stopped';
export type Run = {
    id: string;
    title: string;
    subject: string;
    team: string;
    agent: string;
    status: RunStatus;
    time: string;
    cost: string;
    initials: string;
    version: number;
    note?: string;
    decision?: string;
};
export const initialRuns: Run[] = [
    { id: 'RUN-1048', title: 'Resolve invoice discrepancy', subject: 'Meridian Supply · INV-2026-0842', team: 'Finance', agent: 'Invoice resolution', status: 'Review', time: '10:42', cost: '$0.024', initials: 'MS', version: 1 },
    { id: 'RUN-1047', title: 'Prepare new-hire onboarding', subject: 'Alex Morgan · Operations analyst', team: 'People', agent: 'Employee onboarding', status: 'Completed', time: '10:38', cost: '$0.018', initials: 'AM', version: 1 },
    { id: 'RUN-1046', title: 'Review software access request', subject: 'Jordan Lee · Analytics workspace', team: 'IT', agent: 'Access review', status: 'Review', time: '10:35', cost: '$0.012', initials: 'JL', version: 1 },
    { id: 'RUN-1045', title: 'Match purchase order to invoice', subject: 'Northline Logistics · INV-5816', team: 'Finance', agent: 'Invoice resolution', status: 'Failed', time: '10:31', cost: '$0.031', initials: 'NL', version: 1 },
    { id: 'RUN-1044', title: 'Prepare equipment handover', subject: 'Sam Rivera · New starter', team: 'People', agent: 'Employee onboarding', status: 'Running', time: '10:29', cost: '$0.009', initials: 'SR', version: 1 },
    { id: 'RUN-1043', title: 'Validate supplier invoice', subject: 'Cedar Office · INV-0039', team: 'Finance', agent: 'Invoice resolution', status: 'Completed', time: '10:24', cost: '$0.016', initials: 'CO', version: 1 },
    { id: 'RUN-1042', title: 'Prepare policy acknowledgement', subject: 'Taylor Brooks · Field operations', team: 'People', agent: 'Employee onboarding', status: 'Completed', time: '10:19', cost: '$0.011', initials: 'TB', version: 1 },
    { id: 'RUN-1041', title: 'Review temporary access request', subject: 'Casey Patel · Reporting workspace', team: 'IT', agent: 'Access review', status: 'Review', time: '10:16', cost: '$0.014', initials: 'CP', version: 1 }
];
export const agents = [
    { name: 'Invoice resolution', role: 'Finance operations', description: 'Reconcile invoices, verify policy, and route exceptions with supporting evidence.', icon: 'receipt', color: 'blue', version: 'v0.4.2', tools: ['Purchase orders', 'Receipt records', 'Policy search'], authority: 'Read records and draft resolutions. Human approval before any write.' },
    { name: 'Employee onboarding', role: 'People operations', description: 'Coordinate start dates, equipment requests, and policy acknowledgements.', icon: 'people', color: 'violet', version: 'v0.2.1', tools: ['HR directory', 'Equipment queue', 'Document templates'], authority: 'Prepare checklists. Manager approval for account or equipment provisioning.' },
    { name: 'Access review', role: 'IT operations', description: 'Check access requests against role, manager approval, and entitlement policy.', icon: 'shield', color: 'green', version: 'v0.3.0', tools: ['Identity directory', 'Access policy', 'Service desk'], authority: 'Recommend scoped access. Never grant privileges without an approved request.' }
];
export const trace = [
    { title: 'Received invoice', tool: 'document.extract', duration: '1.2 s', description: 'Extracted 6 line items from INV-2026-0842. Vendor and currency matched.', status: 'done' },
    { title: 'Retrieved supporting records', tool: 'erp.read_purchase_order', duration: '0.8 s', description: 'PO-4821 and receipt GRN-0912 retrieved from the fixture tenant.', status: 'done' },
    { title: 'Found a quantity mismatch', tool: 'invoice.compare', duration: '0.1 s', description: 'Invoice: 120 units. Receipt: 100 units. Difference: $240.00.', status: 'done' },
    { title: 'Checked exception policy', tool: 'knowledge.retrieve', duration: '0.7 s', description: 'AP policy v3.2, §4.1 requires approval when quantity variance exceeds 5%.', status: 'done' },
    { title: 'Waiting for your approval', tool: 'approval.request', duration: 'Paused', description: 'Proposed action: accept $1,200.00 and request a $240.00 credit. No payment will be issued.', status: 'waiting' }
];
export const documents = [
    { name: 'Accounts payable policy', type: 'Policy', scope: 'Finance', version: 'v3.2', text: '§4.1 — Quantity variance above 5% requires a finance reviewer. Match against received quantity. Never release payment on the basis of invoice text alone.', source: 'ap-policy-v3.2.pdf', effective: '2026-10-01' },
    { name: 'Meridian Supply invoice', type: 'Invoice', scope: 'Finance', version: 'INV-2026-0842', text: '120 units × $12.00 = $1,440.00. Purchase order: PO-4821. Received quantity: 100 units according to GRN-0912.', source: 'invoice-0842.pdf', effective: '2026-10-20' },
    { name: 'Application access policy', type: 'Policy', scope: 'IT', version: 'v2.1', text: 'Workspace access requires a manager-approved ticket, named scope, and an expiration date. Privileged roles require separate security review.', source: 'access-policy.pdf', effective: '2026-09-15' },
    { name: 'New starter checklist', type: 'Checklist', scope: 'People', version: 'v1.4', text: 'Verify start date, prepare equipment, request manager-approved accounts, and record acknowledgement of the applicable policies.', source: 'starter-checklist.pdf', effective: '2026-08-01' }
];
