--
-- PostgreSQL database dump
--

\restrict dHcm9BRTMiNoeZ8t72TnOlb6KjNu5aMyn7CAgOxJbstFBuF5QZgAg6wkLgXuZVH

-- Dumped from database version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)
-- Dumped by pg_dump version 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comments (
    id integer NOT NULL,
    feature_id integer NOT NULL,
    case_id integer NOT NULL,
    layer_id integer NOT NULL,
    user_id integer NOT NULL,
    comment text NOT NULL,
    attachment_data bytea,
    attachment_filename character varying(255),
    attachment_content_type character varying(100),
    created_at timestamp without time zone DEFAULT now(),
    feature_number integer NOT NULL,
    parent_comment_id integer,
    root_comment_id integer
);


--
-- Name: comments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comments_id_seq OWNED BY public.comments.id;


--
-- Name: features; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.features (
    id integer NOT NULL,
    feature_number integer NOT NULL,
    layer_id integer,
    case_id integer,
    name text,
    geom public.geometry(Geometry,4326),
    geometry_type character varying,
    radius double precision,
    properties json,
    image_data bytea,
    created_by integer,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: features_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.features_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: features_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.features_id_seq OWNED BY public.features.id;


--
-- Name: geo_news_search_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.geo_news_search_history (
    id integer NOT NULL,
    user_id integer NOT NULL,
    case_id integer NOT NULL,
    layer_id integer NOT NULL,
    feature_number integer NOT NULL,
    feature_name text NOT NULL,
    keywords json NOT NULL,
    start_date timestamp with time zone,
    end_date timestamp with time zone,
    max_results integer NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: geo_news_search_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.geo_news_search_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: geo_news_search_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.geo_news_search_history_id_seq OWNED BY public.geo_news_search_history.id;


--
-- Name: image_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.image_records (
    id character varying NOT NULL,
    file_hash character varying NOT NULL,
    layer_id integer NOT NULL,
    image_data bytea NOT NULL,
    filename character varying NOT NULL,
    content_type character varying(50),
    location public.geography(Point,4326),
    metadata json,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: layers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.layers (
    id integer NOT NULL,
    case_id integer NOT NULL,
    name character varying(100) NOT NULL,
    layer_type character varying(50),
    visible boolean,
    created_at timestamp without time zone DEFAULT now(),
    file_hash character varying(64)
);


--
-- Name: layers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.layers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: layers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.layers_id_seq OWNED BY public.layers.id;


--
-- Name: reference_features; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reference_features (
    id integer NOT NULL,
    reference_layer_id integer NOT NULL,
    name text,
    geom public.geometry(Geometry,4326),
    properties json DEFAULT '{}'::json,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: reference_features_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reference_features_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reference_features_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reference_features_id_seq OWNED BY public.reference_features.id;


--
-- Name: reference_layers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reference_layers (
    id integer NOT NULL,
    name text NOT NULL,
    layer_type character varying NOT NULL,
    description text,
    visible boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: reference_layers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reference_layers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reference_layers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reference_layers_id_seq OWNED BY public.reference_layers.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(255) NOT NULL,
    password text NOT NULL,
    full_name character varying(100),
    role character varying(30) NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    last_login timestamp without time zone,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['Admin'::character varying, 'Officer'::character varying, 'Analyst'::character varying, 'Viewer'::character varying])::text[])))
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
-- Name: comments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments ALTER COLUMN id SET DEFAULT nextval('public.comments_id_seq'::regclass);


--
-- Name: features id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.features ALTER COLUMN id SET DEFAULT nextval('public.features_id_seq'::regclass);


--
-- Name: geo_news_search_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geo_news_search_history ALTER COLUMN id SET DEFAULT nextval('public.geo_news_search_history_id_seq'::regclass);


--
-- Name: layers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layers ALTER COLUMN id SET DEFAULT nextval('public.layers_id_seq'::regclass);


--
-- Name: reference_features id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_features ALTER COLUMN id SET DEFAULT nextval('public.reference_features_id_seq'::regclass);


--
-- Name: reference_layers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_layers ALTER COLUMN id SET DEFAULT nextval('public.reference_layers_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
20260727_01
\.


--
-- Data for Name: comments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.comments (id, feature_id, case_id, layer_id, user_id, comment, attachment_data, attachment_filename, attachment_content_type, created_at, feature_number, parent_comment_id, root_comment_id) FROM stdin;
211	702804	1	371	7	[News]\nTitle: UP Weather: Heavy Rain Alert In 28 Districts From Agra To Prayagraj As Monsoon Remains Active\nSource: ABP Live English\nPublished: 02 Sep 2026\nURL: https://news.google.com/rss/articles/CBMi0wFBVV95cUxObEZvVlRacGo0dWx3ZkNZSDBWQk9pVGsxRGVGZFZQb2ZHSUpfOE0xY3dwbnpfQnNKMHpyUVJUODRUM3B6QkVraTNfZFBVRTlSU295aFNZWmYtclEtWW9kYjQ3T3pxbGc0UWNqX2szLTI2VnpNeFE5WWxKRnRwWDM3emVvN1ZLMkVSUGgwc0tTak5JU1F6TC03LUhrcV9ZcUtlTHFsYWtfTWNta0I0b0RKS0EyOF9RZEhDRkY0N1FfenJrbkp4dXRFaUlBOFZDRTVNNDY40gHYAUFVX3lxTE1xOVRHeFUwcnNXXzNCd2E0b2MxQWJxMG91bm1GY1hpTldNclF6VDVfNTlWbkVvWEVObXZMUUNIdGltcmUzWHBlZ3pkSWxSVkV0QU1CQUFpT2JEZzZiYmYzNTlna3BoQUwxSHl6b3lLR2tYem43dG01UEt0cEdJS0pjdG05NnFER0M0OXZIRFdjY1RBa3RiSGxvUjJVV0NoeHlNTnNVd2dBeFpiLS1KRm50UDVsT21nVmRPcm9rU2ZDY0dnekNHN3I2U09GWVcxOHZIYzBBd2w3MQ?oc=5\nSummary: UP Weather: Heavy Rain Alert In 28 Districts From Agra To Prayagraj As Monsoon Remains Active ABP Live English	\N	\N	\N	2026-09-04 04:40:46.691655	1	\N	\N
212	702804	1	371	7	[News]\nTitle: Rajasthan: Weather to Change in Jaipur, Bharatpur and Several Districts Between September 3–7; Heavy Rain in some areas\nSource: Patrika News\nPublished: 03 Sep 2026\nURL: https://news.google.com/rss/articles/CBMinwFBVV95cUxQNTFETjFZWE9LdUJmUEZDUVUzU2VFT3U4NmtockJyb2VYOEczc2FkQ0VxXzFLbXZzYmIydUhqaU40UFBMQmlsMFRyT3VoV0Zfd21yUnhvQUdDM08xMVI4WVZJZFpWQlZkMW9tOVI3dnFMQlBFV3hPRGlVNjFyRklLRXpORFRZZjNwenpDQnNwVi1EdWdOSmk0bXdLU3ZRSjDSAaQBQVVfeXFMTmY3TXBJelFWTXBqeVFWRFpTcEtJUEVNM0h4VnBvbDNMbF9wT0hYWWlCUXFlNkZEQ21hV0V6X0hjYlYycENiLUIwUUxCYXZwa21TTFdjVHZOQzdTREVvZ1BJYTVFbThVNEVPY25ScnRVOVYzRzd6ME84NzhuRHpJSTJGMEd1SkNYZThfQmhXVU1GSFFfN0s2NFE4ZE9QaldEZktzR0g?oc=5\nSummary: Rajasthan: Weather to Change in Jaipur, Bharatpur and Several Districts Between September 3–7; Heavy Rain in some areas Patrika News	\N	\N	\N	2026-09-04 04:42:28.828138	1	\N	\N
\.


--
-- Data for Name: features; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.features (id, feature_number, layer_id, case_id, name, geom, geometry_type, radius, properties, image_data, created_by, created_at, updated_at) FROM stdin;
702804	1	371	1	12	0103000020E610000001000000410000003514A54B21295340ED50B9816E5B3D40BC4F95FCB2165340428080D532583D4084D2057A75045340EB9FF465884E3D4072EF1BF298F25240491C18D6883E3D4000A8BF594CE1524076636F825E283D406FC381D8BCD0524072DC8BF6430C3D4005F24B3E15C15240EE45AB2F83EA3C4013C56E857DB25240BABB9DB074C33C408F181C631AA552403F97FC6B7E973C407677C9E70C9952409A845A8A12673C4018D85E30728E524083B07612AE323C409305842863855240804CA379D7FA3B400912DA5DF47D5240D1E27F221DC03B40344F7CE335785240A002EACF13833B406173C944337452402182A41155443B40AC7F3386F37152406E9EB9AF7D043B404877AB3279715240763C11192CC43A402E202B74C2725240913924D9FE833A40B2C8DF35C9755240E45E281893443A403396894E837A5240FBA48C2883063A407409BFB1E28052402688272465CA39404E14E8A6D5885240DCD3139BC9903940C890EB0447925240CB5AE4553A5A39404EEEB1711E9D524028ED932C3927394094F2C5A440A952401CC562F33EF83840F8A17EAC8FB65240F90CAB7EBACD384088A03A35EBC452404D1F98BE0FA83840531A4DD230D45240ABA094F396873840B6814E483CE45240E0B02FFC9B6C38407BA090D8E7F452406EA926BD5D573840934D7E8D0C065340BF362DA40D4838402E78B48782175340F1B2F745CF3E38403514A54B2129534048CFF217B83B38403BB0950FC03A5340F1B2F745CF3E3840D6DACB09364C5340BF362DA40D483840EE87B9BE5A5D53406EA926BD5D573840B3A6FB4E066E5340E0B02FFC9B6C3840160EFDC4117E5340ABA094F396873840E1870F62578D53404D1F98BE0FA838407086CBEAB29B5340F90CAB7EBACD3840D63584F201A953401CC562F33EF838401B3A982524B5534028ED932C39273940A1975E92FBBF5340CA5AE4553A5A39401B1462F06CC95340DCD3139BC9903940F51E8BE55FD153402688272465CA39403692C048BFD75340FBA48C2883063A40B75F6A6179DC5340E45E281893443A403B081F2380DF5340903924D9FE833A4021B19E64C9E05340763C11192CC43A40BDA816114FE053406C9EB9AF7D043B4009B580520FDE53402182A41155443B4035D9CDB30CDA5340A002EACF13833B40601670394ED45340D1E27F221DC03B40D622C66EDFCC5340804CA379D7FA3B405150EB66D0C3534083B07612AE323C40F3B080AF35B953409A845A8A12673C40DA0F2E3428AD53403F97FC6B7E973C405663DB11C59F5340BABB9DB074C33C406436FE582D915340EE45AB2F83EA3C40FA64C8BE8581534072DC8BF6430C3D406A808A3DF670534076636F825E283D40F8382EA5A95F5340491C18D6883E3D40E755441DCD4D5340EB9FF465884E3D40AED8B49A8F3B5340428080D532583D403514A54B21295340ED50B9816E5B3D40	Polygon	\N	{"name": "12", "type": "circle", "color": "#ea580c", "category": "Terrorist", "radius": 284874.965640437, "center": {"lat": 26.795216371785596, "lng": 76.6426571952914}}	\N	7	2026-09-04 04:16:55.125915	2026-09-04 04:16:55.125915
702911	2	375	1	hgftfc	0103000020E610000001000000050000004D4D8237A420534093718C648F5032404D4D8237A4205340124DA08845103340005471E316BE5340124DA08845103340005471E316BE534093718C648F5032404D4D8237A420534093718C648F503240	Rectangle	\N	{"name": "hgftfc", "type": "rectangle", "color": "#ea3395", "category": "Surveillance"}	\N	7	2026-09-04 04:52:57.07662	2026-09-04 04:52:57.07662
\.


--
-- Data for Name: geo_news_search_history; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.geo_news_search_history (id, user_id, case_id, layer_id, feature_number, feature_name, keywords, start_date, end_date, max_results, created_at) FROM stdin;
62	7	1	371	1	12	["Rain"]	2026-08-27 17:00:00-07	2026-09-03 17:00:00-07	10	2026-09-04 04:42:23.182425-07
\.


--
-- Data for Name: image_records; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.image_records (id, file_hash, layer_id, image_data, filename, content_type, location, metadata, created_at) FROM stdin;
\.


--
-- Data for Name: layers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.layers (id, case_id, name, layer_type, visible, created_at, file_hash) FROM stdin;
375	1	Auto Layer 2	auto	t	2026-09-04 04:52:57.07662	\N
371	1	Auto Layer 1	auto	t	2026-09-04 04:16:55.125915	\N
\.


--
-- Data for Name: reference_features; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.reference_features (id, reference_layer_id, name, geom, properties, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: reference_layers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.reference_layers (id, name, layer_type, description, visible, created_at, updated_at) FROM stdin;
1	State Boundaries	boundary	India state boundaries	f	2026-08-10 05:53:30.250755	2026-08-10 05:53:30.250755
2	Districts	point	India district locations	f	2026-08-10 05:53:30.250755	2026-08-10 05:53:30.250755
3	Metro Lines	line	Metro rail lines across India	f	2026-08-10 05:53:30.250755	2026-08-10 05:53:30.250755
4	Railway Lines	line	Railway lines across India	f	2026-08-10 05:53:30.250755	2026-08-10 05:53:30.250755
\.


--
-- Data for Name: spatial_ref_sys; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.spatial_ref_sys (srid, auth_name, auth_srid, srtext, proj4text) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users (id, username, email, password, full_name, role, created_at, last_login) FROM stdin;
1	user	user@gmail.com	$2b$12$KRvBUnMuQ9t.gws7jkTB/u5Q2Yg.BIOzqCBlKOHWC2q9n5ClM2e7O	User Name	Admin	2026-07-31 05:07:24.093042	2026-09-03 02:49:42.170665
2	faaaaaa	faaaaaa@example.com	$2b$12$ES2QUV8uS.WuKtEz0XUpWOVzuL3sliYw8kxMdHYMptBLaXgKs2306	Shreya shahane	Admin	2026-07-31 05:53:11.415133	\N
3	faaaaaaaaaa	faaaaaaaaaa@example.com	$2b$12$RImSPJpOAD5KAHvXgD6qKeCrYivr5G8HFz9mUtTYhaTO0YbzpNajG	Sahil Chaudhari	Admin	2026-07-31 06:00:06.455379	\N
4	test_analyst	test_analyst@test.com	$2b$12$8QmGi9Di1WqfV4u3RkVuE.EzAu1eRotQeWWXpbQzqcTkTHfTwgx9G	Test Analyst	Analyst	2026-08-05 05:28:21.128742	2026-08-05 05:29:58.50912
5	parth	parth@example.com	$2b$12$Zw5vilKFyfys7Fs8RPFiqeAo4KfhQ6DWpYhM6w6WNbOFjWgqv9srO	Parth kulkarni	Admin	2026-08-06 03:27:07.035157	2026-09-01 23:56:11.16766
6	shreya	shreya@gmail.com	$2b$12$eCnhm00uzwvZAy4RS6449OCch7agy6nLuX8d3AxueH2MuJws7O6GW	Shreya Shahane	Admin	2026-08-10 04:24:56.033789	2026-09-03 00:22:38.52767
7	sahil	sahil@gmail.com	$2b$12$lK8VB6pXaKyOzX7EvJDpdO3LwE8BZuEbDeXACFmh9oe3rjFTV83C.	Sahil Chaudhari	Viewer	2026-09-01 22:24:27.274573	2026-09-03 01:00:23.472998
\.


--
-- Name: comments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.comments_id_seq', 212, true);


--
-- Name: features_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.features_id_seq', 702911, true);


--
-- Name: geo_news_search_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.geo_news_search_history_id_seq', 62, true);


--
-- Name: layers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.layers_id_seq', 375, true);


--
-- Name: reference_features_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.reference_features_id_seq', 1, false);


--
-- Name: reference_layers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.reference_layers_id_seq', 4, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.users_id_seq', 7, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: comments comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (id);


--
-- Name: features features_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.features
    ADD CONSTRAINT features_pkey PRIMARY KEY (id);


--
-- Name: geo_news_search_history geo_news_search_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geo_news_search_history
    ADD CONSTRAINT geo_news_search_history_pkey PRIMARY KEY (id);


--
-- Name: image_records image_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_records
    ADD CONSTRAINT image_records_pkey PRIMARY KEY (id);


--
-- Name: layers layers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layers
    ADD CONSTRAINT layers_pkey PRIMARY KEY (id);


--
-- Name: reference_features reference_features_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_features
    ADD CONSTRAINT reference_features_pkey PRIMARY KEY (id);


--
-- Name: reference_layers reference_layers_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_layers
    ADD CONSTRAINT reference_layers_name_key UNIQUE (name);


--
-- Name: reference_layers reference_layers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_layers
    ADD CONSTRAINT reference_layers_pkey PRIMARY KEY (id);


--
-- Name: features uq_feature_case_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.features
    ADD CONSTRAINT uq_feature_case_number UNIQUE (case_id, feature_number);


--
-- Name: layers uq_layers_case_id_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layers
    ADD CONSTRAINT uq_layers_case_id_name UNIQUE (case_id, name);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_comments_feature_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comments_feature_number ON public.comments USING btree (feature_number);


--
-- Name: idx_comments_parent_comment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comments_parent_comment_id ON public.comments USING btree (parent_comment_id);


--
-- Name: idx_features_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_features_geom ON public.features USING gist (geom);


--
-- Name: idx_image_records_location; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_image_records_location ON public.image_records USING gist (location);


--
-- Name: idx_reference_features_geom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_features_geom ON public.reference_features USING gist (geom);


--
-- Name: idx_reference_features_layer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reference_features_layer_id ON public.reference_features USING btree (reference_layer_id);


--
-- Name: ix_comments_root_comment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comments_root_comment_id ON public.comments USING btree (root_comment_id);


--
-- Name: ix_geo_news_search_history_case_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geo_news_search_history_case_id ON public.geo_news_search_history USING btree (case_id);


--
-- Name: ix_geo_news_search_history_layer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geo_news_search_history_layer_id ON public.geo_news_search_history USING btree (layer_id);


--
-- Name: ix_geo_news_search_history_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_geo_news_search_history_user_id ON public.geo_news_search_history USING btree (user_id);


--
-- Name: ix_image_records_file_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_image_records_file_hash ON public.image_records USING btree (file_hash);


--
-- Name: ix_image_records_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_image_records_id ON public.image_records USING btree (id);


--
-- Name: ix_image_records_layer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_image_records_layer_id ON public.image_records USING btree (layer_id);


--
-- Name: ix_layers_file_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_layers_file_hash ON public.layers USING btree (file_hash);


--
-- Name: comments comments_feature_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_feature_id_fkey FOREIGN KEY (feature_id) REFERENCES public.features(id) ON DELETE CASCADE;


--
-- Name: comments comments_layer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_layer_id_fkey FOREIGN KEY (layer_id) REFERENCES public.layers(id) ON DELETE CASCADE;


--
-- Name: comments comments_parent_comment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_parent_comment_id_fkey FOREIGN KEY (parent_comment_id) REFERENCES public.comments(id) ON DELETE CASCADE;


--
-- Name: comments comments_root_comment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_root_comment_id_fkey FOREIGN KEY (root_comment_id) REFERENCES public.comments(id);


--
-- Name: comments comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: features features_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.features
    ADD CONSTRAINT features_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: features features_layer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.features
    ADD CONSTRAINT features_layer_id_fkey FOREIGN KEY (layer_id) REFERENCES public.layers(id) ON DELETE CASCADE;


--
-- Name: reference_features fk_reference_features_layer; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reference_features
    ADD CONSTRAINT fk_reference_features_layer FOREIGN KEY (reference_layer_id) REFERENCES public.reference_layers(id) ON DELETE CASCADE;


--
-- Name: geo_news_search_history geo_news_search_history_layer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geo_news_search_history
    ADD CONSTRAINT geo_news_search_history_layer_id_fkey FOREIGN KEY (layer_id) REFERENCES public.layers(id) ON DELETE CASCADE;


--
-- Name: geo_news_search_history geo_news_search_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.geo_news_search_history
    ADD CONSTRAINT geo_news_search_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: image_records image_records_layer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.image_records
    ADD CONSTRAINT image_records_layer_id_fkey FOREIGN KEY (layer_id) REFERENCES public.layers(id);


--
-- PostgreSQL database dump complete
--

\unrestrict dHcm9BRTMiNoeZ8t72TnOlb6KjNu5aMyn7CAgOxJbstFBuF5QZgAg6wkLgXuZVH

