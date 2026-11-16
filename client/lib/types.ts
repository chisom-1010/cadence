export type ICP = {
  summary: string;
  industries: string[];
  company_size: string;
  regions: string[];
  target_roles: string[];
  keywords: string[];
  pain_points: string[];
  exclusions: string[];
};

export type Competitor = { name: string; domain: string; note: string };

export type Campaign = {
  id: string;
  name: string;
  product_pitch: string;
  icp_description: string;
  icp: ICP | null;
  competitors?: Competitor[] | null;
  status: string;
  created_at: string;
};

export type Lead = {
  id: string;
  campaign_id: string;
  company_name: string;
  domain: string | null;
  contact_name: string | null;
  contact_role: string | null;
  contact_email: string | null;
  source: "search" | "csv" | "seed";
  research_summary: string | null;
  fit_score: number | null;
  fit_reason: string | null;
  personalization_hook: string | null;
  status: string;
  error: string | null;
  created_at: string;
  campaigns?: { name: string } | null;
};

export type EmailStatus = "draft" | "approved" | "rejected" | "sent" | "failed";

export type Email = {
  id: string;
  lead_id: string;
  campaign_id: string;
  subject: string;
  body: string;
  status: EmailStatus;
  sent_to: string | null;
  error: string | null;
  approved_at: string | null;
  sent_at: string | null;
  created_at: string;
  leads: {
    company_name: string;
    domain: string | null;
    contact_name: string | null;
    contact_email: string | null;
    fit_score: number | null;
    status: string;
    research_summary: string | null;
    personalization_hook: string | null;
    fit_reason: string | null;
  } | null;
};

export type ReplyLabel = "interested" | "question" | "not_interested" | "out_of_office" | "unsubscribe";

export type Reply = {
  id: string;
  lead_id: string;
  body: string;
  label: ReplyLabel | null;
  is_hot: boolean;
  reason: string | null;
  simulated: boolean;
  received_at: string;
  leads: { company_name: string; contact_name: string | null; domain: string | null } | null;
};

export type Me = {
  id: string;
  email: string;
  demo_mode: boolean;
  demo_recipient: string | null;
  mail_configured: boolean;
};

export type EmailState = "found" | "guessed" | "role_address" | "no_mail_server" | "unknown";

export type Contact = {
  id: string;
  lead_id: string;
  full_name: string;
  role: string | null;
  email: string | null;
  email_status: EmailState;
  source: "website" | "seed" | "manual";
  is_primary: boolean;
};
