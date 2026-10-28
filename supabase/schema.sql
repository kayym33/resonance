-- t1ld3 sync schema. Paste into the Supabase SQL editor and run it; it's safe
-- to run again after updating this file.
--
-- Everything a user syncs lives in one table: to-dos, calendar events,
-- settings, launcher commands, recipes and their profile. Each row is one record
-- of a kind, holding its fields as JSON.

create table if not exists public.items (
  user_id uuid not null default auth.uid()
    references auth.users (id) on delete cascade,
  kind text not null
    check (kind in ('task', 'event', 'setting', 'commands', 'profile', 'recipe')),
  id text not null,
  data jsonb not null default '{}'::jsonb,
  -- Deleted records are kept as tombstones so the deletion syncs too.
  deleted boolean not null default false,
  -- When the edit was made, by the editing device's clock.
  updated_at timestamptz not null,
  -- When the server stored it; devices pull everything newer than the
  -- last value they saw. Set by the trigger below, never by clients.
  server_updated_at timestamptz not null default now(),
  primary key (user_id, kind, id)
);

-- "create table if not exists" leaves an older table's kinds alone, so
-- replace the check too. Safe to run again.
alter table public.items drop constraint if exists items_kind_check;
alter table public.items add constraint items_kind_check
  check (kind in ('task', 'event', 'setting', 'commands', 'profile', 'recipe'));

create index if not exists items_user_server_updated_at
  on public.items (user_id, server_updated_at);

-- Last write wins: an edit that arrives late (say from a laptop that was
-- offline) can't overwrite a newer one.
create or replace function public.items_before_write()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and new.updated_at < old.updated_at then
    return old;
  end if;
  new.server_updated_at := now();
  return new;
end;
$$;

drop trigger if exists items_before_write on public.items;
create trigger items_before_write
  before insert or update on public.items
  for each row execute function public.items_before_write();

-- Each signed-in user sees and changes only their own rows.
alter table public.items enable row level security;

drop policy if exists "Users manage their own items" on public.items;
create policy "Users manage their own items"
  on public.items
  for all
  to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

revoke all on public.items from anon;
grant select, insert, update, delete on public.items to authenticated;

-- The phone app (phone/). Run this section too before setting it up;
-- see phone/README.md.

-- Phones that turned on notifications, for web push.
create table if not exists public.push_subscriptions (
  user_id uuid not null default auth.uid()
    references auth.users (id) on delete cascade,
  endpoint text not null,
  p256dh text not null,
  auth text not null,
  -- So the server knows when "09:30" is for this phone.
  time_zone text not null default 'UTC',
  created_at timestamptz not null default now(),
  primary key (user_id, endpoint)
);

-- Pushes to send later: cooking timers started on the phone, which iOS
-- pauses once it's in the background. The reminders function sends them.
create table if not exists public.scheduled_pushes (
  user_id uuid not null default auth.uid()
    references auth.users (id) on delete cascade,
  id text not null,
  send_at timestamptz not null,
  title text not null,
  body text not null default '',
  primary key (user_id, id)
);

create index if not exists scheduled_pushes_send_at
  on public.scheduled_pushes (send_at);

-- Event reminders already pushed, so each goes out once. Only the
-- reminders function (server side) reads or writes it: no policies.
create table if not exists public.sent_reminders (
  user_id uuid not null references auth.users (id) on delete cascade,
  key text not null,
  sent_at timestamptz not null default now(),
  primary key (user_id, key)
);

alter table public.push_subscriptions enable row level security;
alter table public.scheduled_pushes enable row level security;
alter table public.sent_reminders enable row level security;

drop policy if exists "Users manage their own push subscriptions" on public.push_subscriptions;
create policy "Users manage their own push subscriptions"
  on public.push_subscriptions
  for all
  to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

drop policy if exists "Users manage their own scheduled pushes" on public.scheduled_pushes;
create policy "Users manage their own scheduled pushes"
  on public.scheduled_pushes
  for all
  to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

revoke all on public.push_subscriptions, public.scheduled_pushes, public.sent_reminders from anon;
revoke all on public.sent_reminders from authenticated;
grant select, insert, update, delete
  on public.push_subscriptions, public.scheduled_pushes to authenticated;
