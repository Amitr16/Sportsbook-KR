--
-- PostgreSQL database dump
--

-- Dumped from database version 16.6
-- Dumped by pg_dump version 16.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bet_slip_bets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bet_slip_bets (
    bet_slip_id integer NOT NULL,
    bet_id integer NOT NULL
);

--
-- Name: bet_slips; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bet_slips (
    id integer NOT NULL,
    user_id integer NOT NULL,
    total_stake double precision NOT NULL,
    total_odds double precision NOT NULL,
    potential_return double precision NOT NULL,
    bet_type character varying(8),
    status character varying(10),
    actual_return double precision,
    settled_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    sportsbook_operator_id integer
);

--
-- Name: bet_slips_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bet_slips_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: bet_slips_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bet_slips_id_seq OWNED BY public.bet_slips.id;

--
-- Name: bets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bets (
    id integer NOT NULL,
    user_id integer NOT NULL,
    match_id character varying(50),
    match_name character varying(200),
    selection character varying(100),
    bet_selection character varying(100),
    stake double precision NOT NULL,
    odds double precision NOT NULL,
    potential_return double precision NOT NULL,
    status character varying(20),
    bet_type character varying(20),
    actual_return double precision,
    settled_at timestamp without time zone,
    combo_selections text,
    event_time timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    sport_name character varying(50),
    bet_timing character varying(20) DEFAULT 'pregame'::character varying,
    is_active boolean DEFAULT true,
    market text,
    sportsbook_operator_id integer
);

--
-- Name: bets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: bets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bets_id_seq OWNED BY public.bets.id;

--
-- Name: disabled_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disabled_events (
    id integer NOT NULL,
    event_key text,
    sport text,
    event_name text,
    market text,
    is_disabled boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

--
-- Name: disabled_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.disabled_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: disabled_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.disabled_events_id_seq OWNED BY public.disabled_events.id;

--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id integer NOT NULL,
    goalserve_id character varying(20) NOT NULL,
    static_id character varying(20),
    home_team_id integer NOT NULL,
    away_team_id integer NOT NULL,
    sport_id integer NOT NULL,
    league_id integer NOT NULL,
    commence_time timestamp without time zone NOT NULL,
    venue character varying(100),
    status character varying(20),
    home_score integer,
    away_score integer,
    current_period character varying(20),
    match_time character varying(10),
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;

--
-- Name: leagues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leagues (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    country character varying(50),
    sport_id integer NOT NULL,
    goalserve_id character varying(20),
    is_active boolean
);

--
-- Name: leagues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leagues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: leagues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leagues_id_seq OWNED BY public.leagues.id;

--
-- Name: markets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.markets (
    id integer NOT NULL,
    event_id integer NOT NULL,
    name character varying(100) NOT NULL,
    market_type character varying(50) NOT NULL,
    is_active boolean
);

--
-- Name: markets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.markets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: markets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.markets_id_seq OWNED BY public.markets.id;

--
-- Name: operator_wallets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operator_wallets (
    id integer NOT NULL,
    operator_id integer NOT NULL,
    wallet_type character varying(50) NOT NULL,
    current_balance real DEFAULT 0.0 NOT NULL,
    initial_balance real DEFAULT 0.0 NOT NULL,
    leverage_multiplier real DEFAULT 1.0 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

--
-- Name: operator_wallets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.operator_wallets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: operator_wallets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.operator_wallets_id_seq OWNED BY public.operator_wallets.id;

--
-- Name: outcomes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outcomes (
    id integer NOT NULL,
    market_id integer NOT NULL,
    name character varying(50) NOT NULL,
    odds double precision NOT NULL,
    is_active boolean,
    updated_at timestamp without time zone
);

--
-- Name: outcomes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.outcomes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: outcomes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.outcomes_id_seq OWNED BY public.outcomes.id;

--
-- Name: revenue_calculations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.revenue_calculations (
    id integer NOT NULL,
    operator_id integer NOT NULL,
    calculation_date date NOT NULL,
    total_revenue real DEFAULT 0.0 NOT NULL,
    total_bets_amount real DEFAULT 0.0 NOT NULL,
    total_payouts real DEFAULT 0.0 NOT NULL,
    bookmaker_own_share real DEFAULT 0.0 NOT NULL,
    kryzel_fee_from_own real DEFAULT 0.0 NOT NULL,
    bookmaker_net_own real DEFAULT 0.0 NOT NULL,
    remaining_profit real DEFAULT 0.0 NOT NULL,
    bookmaker_share_60 real DEFAULT 0.0 NOT NULL,
    community_share_30 real DEFAULT 0.0 NOT NULL,
    kryzel_share_10 real DEFAULT 0.0 NOT NULL,
    bookmaker_own_loss real DEFAULT 0.0 NOT NULL,
    remaining_loss real DEFAULT 0.0 NOT NULL,
    bookmaker_loss_70 real DEFAULT 0.0 NOT NULL,
    community_loss_30 real DEFAULT 0.0 NOT NULL,
    total_bookmaker_earnings real DEFAULT 0.0 NOT NULL,
    calculation_metadata text,
    processed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

--
-- Name: revenue_calculations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.revenue_calculations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: revenue_calculations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.revenue_calculations_id_seq OWNED BY public.revenue_calculations.id;

--
-- Name: shim_demo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shim_demo (
    id integer NOT NULL,
    enabled boolean,
    name text
);

--
-- Name: shim_demo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.shim_demo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: shim_demo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.shim_demo_id_seq OWNED BY public.shim_demo.id;

--
-- Name: sports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sports (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    key character varying(20) NOT NULL,
    icon character varying(10),
    is_active boolean,
    sort_order integer
);

--
-- Name: sports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: sports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sports_id_seq OWNED BY public.sports.id;

--
-- Name: sportsbook_operators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sportsbook_operators (
    id integer NOT NULL,
    sportsbook_name character varying(100) NOT NULL,
    login character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    email character varying(120),
    subdomain character varying(50) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
    total_revenue double precision DEFAULT 0.0,
    commission_rate double precision DEFAULT 0.05,
    settings text
);

--
-- Name: sportsbook_operators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sportsbook_operators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: sportsbook_operators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sportsbook_operators_id_seq OWNED BY public.sportsbook_operators.id;

--
-- Name: sportsbook_themes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sportsbook_themes (
    id integer NOT NULL,
    sportsbook_operator_id integer NOT NULL,
    theme_name character varying(100) DEFAULT 'default'::character varying,
    primary_color character varying(7) DEFAULT '#1e40af'::character varying,
    secondary_color character varying(7) DEFAULT '#3b82f6'::character varying,
    accent_color character varying(7) DEFAULT '#f59e0b'::character varying,
    background_color character varying(7) DEFAULT '#ffffff'::character varying,
    text_color character varying(7) DEFAULT '#1f2937'::character varying,
    font_family character varying(100) DEFAULT 'Inter, sans-serif'::character varying,
    logo_url character varying(500),
    banner_image_url character varying(500),
    custom_css text,
    layout_style character varying(50) DEFAULT 'modern'::character varying,
    button_style character varying(50) DEFAULT 'rounded'::character varying,
    card_style character varying(50) DEFAULT 'shadow'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    logo_type text DEFAULT 'default'::text,
    sportsbook_name text DEFAULT 'Your Sportsbook'::text
);

--
-- Name: sportsbook_themes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sportsbook_themes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: sportsbook_themes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sportsbook_themes_id_seq OWNED BY public.sportsbook_themes.id;

--
-- Name: super_admins; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.super_admins (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    email character varying(120) NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login timestamp without time zone,
    permissions text
);

--
-- Name: super_admins_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.super_admins_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: super_admins_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.super_admins_id_seq OWNED BY public.super_admins.id;

--
-- Name: teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teams (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    short_name character varying(20),
    country character varying(50),
    sport_id integer NOT NULL,
    goalserve_id character varying(20),
    logo_url character varying(255)
);

--
-- Name: teams_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.teams_id_seq OWNED BY public.teams.id;

--
-- Name: theme_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.theme_templates (
    id integer NOT NULL,
    template_name character varying(100) NOT NULL,
    display_name character varying(100) NOT NULL,
    description text,
    preview_image_url character varying(500),
    primary_color character varying(7) NOT NULL,
    secondary_color character varying(7) NOT NULL,
    accent_color character varying(7) NOT NULL,
    background_color character varying(7) NOT NULL,
    text_color character varying(7) NOT NULL,
    font_family character varying(100) NOT NULL,
    layout_style character varying(50) NOT NULL,
    button_style character varying(50) NOT NULL,
    card_style character varying(50) NOT NULL,
    custom_css text,
    is_premium boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

--
-- Name: theme_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.theme_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: theme_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.theme_templates_id_seq OWNED BY public.theme_templates.id;

--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    bet_id integer,
    amount double precision NOT NULL,
    transaction_type character varying(20) NOT NULL,
    description character varying(200),
    balance_before double precision NOT NULL,
    balance_after double precision NOT NULL,
    created_at timestamp without time zone,
    sportsbook_operator_id integer
);

--
-- Name: transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transactions_id_seq OWNED BY public.transactions.id;

--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(80) NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(255) NOT NULL,
    balance double precision,
    created_at timestamp without time zone,
    last_login timestamp without time zone,
    is_active boolean,
    sportsbook_operator_id integer
);

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

--
-- Name: wallet_daily_balances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wallet_daily_balances (
    id integer NOT NULL,
    wallet_id integer NOT NULL,
    date date NOT NULL,
    opening_balance real NOT NULL,
    closing_balance real NOT NULL,
    daily_pnl real DEFAULT 0.0 NOT NULL,
    total_revenue real DEFAULT 0.0 NOT NULL,
    total_bets_amount real DEFAULT 0.0 NOT NULL,
    total_payouts real DEFAULT 0.0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

--
-- Name: wallet_daily_balances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wallet_daily_balances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: wallet_daily_balances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wallet_daily_balances_id_seq OWNED BY public.wallet_daily_balances.id;

--
-- Name: wallet_transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wallet_transactions (
    id integer NOT NULL,
    wallet_id integer NOT NULL,
    transaction_type character varying(50) NOT NULL,
    amount real NOT NULL,
    balance_before real NOT NULL,
    balance_after real NOT NULL,
    description character varying(500),
    reference_id character varying(100),
    metadata text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);

--
-- Name: wallet_transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wallet_transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: wallet_transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wallet_transactions_id_seq OWNED BY public.wallet_transactions.id;

--
-- Name: bet_slips id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bet_slips ALTER COLUMN id SET DEFAULT nextval('public.bet_slips_id_seq'::regclass);

--
-- Name: bets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bets ALTER COLUMN id SET DEFAULT nextval('public.bets_id_seq'::regclass);

--
-- Name: disabled_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disabled_events ALTER COLUMN id SET DEFAULT nextval('public.disabled_events_id_seq'::regclass);

--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);

--
-- Name: leagues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leagues ALTER COLUMN id SET DEFAULT nextval('public.leagues_id_seq'::regclass);

--
-- Name: markets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.markets ALTER COLUMN id SET DEFAULT nextval('public.markets_id_seq'::regclass);

--
-- Name: operator_wallets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operator_wallets ALTER COLUMN id SET DEFAULT nextval('public.operator_wallets_id_seq'::regclass);

--
-- Name: outcomes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outcomes ALTER COLUMN id SET DEFAULT nextval('public.outcomes_id_seq'::regclass);

--
-- Name: revenue_calculations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_calculations ALTER COLUMN id SET DEFAULT nextval('public.revenue_calculations_id_seq'::regclass);

--
-- Name: shim_demo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shim_demo ALTER COLUMN id SET DEFAULT nextval('public.shim_demo_id_seq'::regclass);

--
-- Name: sports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports ALTER COLUMN id SET DEFAULT nextval('public.sports_id_seq'::regclass);

--
-- Name: sportsbook_operators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_operators ALTER COLUMN id SET DEFAULT nextval('public.sportsbook_operators_id_seq'::regclass);

--
-- Name: sportsbook_themes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_themes ALTER COLUMN id SET DEFAULT nextval('public.sportsbook_themes_id_seq'::regclass);

--
-- Name: super_admins id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.super_admins ALTER COLUMN id SET DEFAULT nextval('public.super_admins_id_seq'::regclass);

--
-- Name: teams id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams ALTER COLUMN id SET DEFAULT nextval('public.teams_id_seq'::regclass);

--
-- Name: theme_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.theme_templates ALTER COLUMN id SET DEFAULT nextval('public.theme_templates_id_seq'::regclass);

--
-- Name: transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions ALTER COLUMN id SET DEFAULT nextval('public.transactions_id_seq'::regclass);

--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);

--
-- Name: wallet_daily_balances id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_daily_balances ALTER COLUMN id SET DEFAULT nextval('public.wallet_daily_balances_id_seq'::regclass);

--
-- Name: wallet_transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_transactions ALTER COLUMN id SET DEFAULT nextval('public.wallet_transactions_id_seq'::regclass);

--
-- Name: bet_slip_bets bet_slip_bets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bet_slip_bets
    ADD CONSTRAINT bet_slip_bets_pkey PRIMARY KEY (bet_slip_id, bet_id);

--
-- Name: bet_slips bet_slips_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bet_slips
    ADD CONSTRAINT bet_slips_pkey PRIMARY KEY (id);

--
-- Name: bets bets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bets
    ADD CONSTRAINT bets_pkey PRIMARY KEY (id);

--
-- Name: disabled_events disabled_events_event_key_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disabled_events
    ADD CONSTRAINT disabled_events_event_key_unique UNIQUE (event_key);

--
-- Name: disabled_events disabled_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disabled_events
    ADD CONSTRAINT disabled_events_pkey PRIMARY KEY (id);

--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);

--
-- Name: leagues leagues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leagues
    ADD CONSTRAINT leagues_pkey PRIMARY KEY (id);

--
-- Name: markets markets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.markets
    ADD CONSTRAINT markets_pkey PRIMARY KEY (id);

--
-- Name: operator_wallets operator_wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operator_wallets
    ADD CONSTRAINT operator_wallets_pkey PRIMARY KEY (id);

--
-- Name: outcomes outcomes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outcomes
    ADD CONSTRAINT outcomes_pkey PRIMARY KEY (id);

--
-- Name: revenue_calculations revenue_calculations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.revenue_calculations
    ADD CONSTRAINT revenue_calculations_pkey PRIMARY KEY (id);

--
-- Name: shim_demo shim_demo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shim_demo
    ADD CONSTRAINT shim_demo_pkey PRIMARY KEY (id);

--
-- Name: sports sports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sports
    ADD CONSTRAINT sports_pkey PRIMARY KEY (id);

--
-- Name: sportsbook_operators sportsbook_operators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_operators
    ADD CONSTRAINT sportsbook_operators_pkey PRIMARY KEY (id);

--
-- Name: sportsbook_themes sportsbook_themes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_themes
    ADD CONSTRAINT sportsbook_themes_pkey PRIMARY KEY (id);

--
-- Name: super_admins super_admins_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.super_admins
    ADD CONSTRAINT super_admins_pkey PRIMARY KEY (id);

--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (id);

--
-- Name: theme_templates theme_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.theme_templates
    ADD CONSTRAINT theme_templates_pkey PRIMARY KEY (id);

--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);

--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

--
-- Name: wallet_daily_balances wallet_daily_balances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_daily_balances
    ADD CONSTRAINT wallet_daily_balances_pkey PRIMARY KEY (id);

--
-- Name: wallet_transactions wallet_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wallet_transactions
    ADD CONSTRAINT wallet_transactions_pkey PRIMARY KEY (id);

--
-- Name: sportsbook_themes fk_sportsbook_themes_operator; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sportsbook_themes
    ADD CONSTRAINT fk_sportsbook_themes_operator FOREIGN KEY (sportsbook_operator_id) REFERENCES public.sportsbook_operators(id);

--
-- PostgreSQL database dump complete
--

