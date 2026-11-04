-- ManaLab — base de données Supabase
-- À coller tel quel dans Supabase › SQL Editor › New query, puis « Run ».
-- On peut le relancer sans danger : tout est écrit pour ne rien casser si ça existe déjà.

-- 1. Les decks de chaque joueur (une ligne par deck, contenu en JSON)
create table if not exists public.decks (
  user_id    uuid        not null references auth.users (id) on delete cascade,
  id         text        not null,
  data       jsonb       not null default '{}'::jsonb,
  deleted    boolean     not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, id),
  constraint deck_size check (pg_column_size(data) < 300000)
);

-- 2. Les réglages de chaque joueur (langues, vues, corrections de rôles…)
create table if not exists public.user_data (
  user_id    uuid        primary key references auth.users (id) on delete cascade,
  prefs      jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  constraint prefs_size check (pg_column_size(prefs) < 200000)
);

-- 3. Les liens de partage courts (manalab.ca/d/abc1234), lisibles par tout le monde
create table if not exists public.shared_decks (
  code       text        primary key check (code ~ '^[a-z0-9]{5,12}$'),
  data       jsonb       not null,
  owner      uuid        references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  constraint shared_size check (pg_column_size(data) < 100000)
);

-- 4. Les corrections de rôles envoyées par les joueurs (pour améliorer l'outil)
create table if not exists public.role_reports (
  id         bigint      generated always as identity primary key,
  card       text        not null check (length(card) < 200),
  roles      jsonb       not null,
  user_id    uuid        references auth.users (id) on delete set null,
  created_at timestamptz not null default now()
);

-- 5. Les signalements de problèmes (bouton « Signaler un problème »)
create table if not exists public.reports (
  id         bigint      generated always as identity primary key,
  kind       text        not null check (length(kind) < 40),
  message    text        not null check (length(message) between 3 and 4000),
  email      text        check (email is null or length(email) < 200),
  context    jsonb       not null default '{}'::jsonb,
  user_id    uuid        references auth.users (id) on delete set null,
  status     text        not null default 'nouveau' check (status in ('nouveau', 'vu', 'corrigé', 'ignoré')),
  created_at timestamptz not null default now(),
  constraint report_ctx_size check (pg_column_size(context) < 60000)
);
alter table public.reports enable row level security;
drop policy if exists "signalements: envoi" on public.reports;
create policy "signalements: envoi" on public.reports for insert
  with check ((user_id is null or user_id = auth.uid()) and status = 'nouveau');
-- (personne ne peut lire les signalements depuis le site : tu les lis dans Table Editor › reports)

-- Sécurité : chaque joueur ne voit et ne modifie que ses propres données
alter table public.decks        enable row level security;
alter table public.user_data    enable row level security;
alter table public.shared_decks enable row level security;
alter table public.role_reports enable row level security;

drop policy if exists "decks: lire les siens"      on public.decks;
drop policy if exists "decks: écrire les siens"    on public.decks;
drop policy if exists "decks: modifier les siens"  on public.decks;
drop policy if exists "decks: effacer les siens"   on public.decks;
create policy "decks: lire les siens"     on public.decks for select using (auth.uid() = user_id);
create policy "decks: écrire les siens"   on public.decks for insert with check (auth.uid() = user_id);
create policy "decks: modifier les siens" on public.decks for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "decks: effacer les siens"  on public.decks for delete using (auth.uid() = user_id);

drop policy if exists "réglages: lire les siens"     on public.user_data;
drop policy if exists "réglages: écrire les siens"   on public.user_data;
drop policy if exists "réglages: modifier les siens" on public.user_data;
create policy "réglages: lire les siens"     on public.user_data for select using (auth.uid() = user_id);
create policy "réglages: écrire les siens"   on public.user_data for insert with check (auth.uid() = user_id);
create policy "réglages: modifier les siens" on public.user_data for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "partage: lecture publique" on public.shared_decks;
drop policy if exists "partage: création"         on public.shared_decks;
create policy "partage: lecture publique" on public.shared_decks for select using (true);
create policy "partage: création"         on public.shared_decks for insert
  with check (owner is null or owner = auth.uid());

drop policy if exists "rôles: envoi" on public.role_reports;
create policy "rôles: envoi" on public.role_reports for insert
  with check (user_id is null or user_id = auth.uid());
-- (personne ne peut lire role_reports depuis le site : tu les consultes dans le tableau de bord)

-- Droit à l'effacement (Loi 25 / LPRPDE) : le joueur supprime lui-même son compte
create or replace function public.delete_my_account()
returns void language sql security definer set search_path = public as $$
  delete from auth.users where id = auth.uid();
$$;
revoke all on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;

-- Pour toi : les corrections de rôles les plus demandées (Table Editor › role_report_summary)
create or replace view public.role_report_summary with (security_invoker = true) as
  select card, roles, count(*) as votes, max(created_at) as last_seen
  from public.role_reports group by card, roles order by votes desc;
revoke all on public.role_report_summary from anon, authenticated;

-- Pour toi : quelques chiffres (SQL Editor › select * from public.stats;)
create or replace view public.stats with (security_invoker = true) as
  select
    (select count(*) from auth.users)                          as comptes,
    (select count(*) from public.decks where not deleted)      as decks,
    (select count(*) from public.shared_decks)                 as liens_partages,
    (select count(*) from public.role_reports)                 as corrections_roles,
    (select count(*) from public.reports where status = 'nouveau') as signalements_nouveaux;
revoke all on public.stats from anon, authenticated;
