--
-- PostgreSQL database dump
--

\restrict f4V0kXucJLOUGJyQnp4hdQ1MzDy7bPa9db41kwkQFlrUTBeU874DKOewn1gRujO

-- Dumped from database version 15.19
-- Dumped by pg_dump version 15.19

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

ALTER TABLE IF EXISTS ONLY public.partido DROP CONSTRAINT IF EXISTS partido_equipo_visitante_id_fkey;
ALTER TABLE IF EXISTS ONLY public.partido DROP CONSTRAINT IF EXISTS partido_equipo_local_id_fkey;
ALTER TABLE IF EXISTS ONLY public.partido DROP CONSTRAINT IF EXISTS partido_competicion_id_fkey;
ALTER TABLE IF EXISTS ONLY public.participacion DROP CONSTRAINT IF EXISTS participacion_equipo_id_fkey;
ALTER TABLE IF EXISTS ONLY public.participacion DROP CONSTRAINT IF EXISTS participacion_competicion_id_fkey;
ALTER TABLE IF EXISTS ONLY public.estadisticaspartido DROP CONSTRAINT IF EXISTS estadisticaspartido_partido_id_fkey;
ALTER TABLE IF EXISTS ONLY public.equipo DROP CONSTRAINT IF EXISTS equipo_confederacion_id_fkey;
ALTER TABLE IF EXISTS ONLY public.competicion DROP CONSTRAINT IF EXISTS competicion_confederacion_id_fkey;
DROP INDEX IF EXISTS public.ix_confederacion_nombre;
ALTER TABLE IF EXISTS ONLY public.partido DROP CONSTRAINT IF EXISTS partido_pkey;
ALTER TABLE IF EXISTS ONLY public.participacion DROP CONSTRAINT IF EXISTS participacion_pkey;
ALTER TABLE IF EXISTS ONLY public.estadisticaspartido DROP CONSTRAINT IF EXISTS estadisticaspartido_pkey;
ALTER TABLE IF EXISTS ONLY public.equipo DROP CONSTRAINT IF EXISTS equipo_pkey;
ALTER TABLE IF EXISTS ONLY public.confederacion DROP CONSTRAINT IF EXISTS confederacion_pkey;
ALTER TABLE IF EXISTS ONLY public.competicion DROP CONSTRAINT IF EXISTS competicion_pkey;
ALTER TABLE IF EXISTS public.partido ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.estadisticaspartido ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.equipo ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.confederacion ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.competicion ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.partido_id_seq;
DROP TABLE IF EXISTS public.partido;
DROP TABLE IF EXISTS public.participacion;
DROP SEQUENCE IF EXISTS public.estadisticaspartido_id_seq;
DROP TABLE IF EXISTS public.estadisticaspartido;
DROP SEQUENCE IF EXISTS public.equipo_id_seq;
DROP TABLE IF EXISTS public.equipo;
DROP SEQUENCE IF EXISTS public.confederacion_id_seq;
DROP TABLE IF EXISTS public.confederacion;
DROP SEQUENCE IF EXISTS public.competicion_id_seq;
DROP TABLE IF EXISTS public.competicion;
DROP TYPE IF EXISTS public.tipoequipo;
DROP TYPE IF EXISTS public.tipocompeticion;
DROP TYPE IF EXISTS public.estadopartido;
--
-- Name: estadopartido; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.estadopartido AS ENUM (
    'VIVO',
    'FINALIZADO',
    'PROGRAMADO'
);


ALTER TYPE public.estadopartido OWNER TO postgres;

--
-- Name: tipocompeticion; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.tipocompeticion AS ENUM (
    'LIGA_NACIONAL',
    'COPA_NACIONAL',
    'INTERNACIONAL_CLUBES',
    'INTERNACIONAL_SELECCIONES'
);


ALTER TYPE public.tipocompeticion OWNER TO postgres;

--
-- Name: tipoequipo; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.tipoequipo AS ENUM (
    'CLUB',
    'SELECCION'
);


ALTER TYPE public.tipoequipo OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: competicion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.competicion (
    nombre character varying NOT NULL,
    logo character varying NOT NULL,
    tipo public.tipocompeticion NOT NULL,
    pais character varying NOT NULL,
    confederacion_id integer,
    id integer NOT NULL
);


ALTER TABLE public.competicion OWNER TO postgres;

--
-- Name: competicion_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.competicion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.competicion_id_seq OWNER TO postgres;

--
-- Name: competicion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.competicion_id_seq OWNED BY public.competicion.id;


--
-- Name: confederacion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.confederacion (
    nombre character varying NOT NULL,
    logo character varying NOT NULL,
    id integer NOT NULL
);


ALTER TABLE public.confederacion OWNER TO postgres;

--
-- Name: confederacion_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.confederacion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.confederacion_id_seq OWNER TO postgres;

--
-- Name: confederacion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.confederacion_id_seq OWNED BY public.confederacion.id;


--
-- Name: equipo; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.equipo (
    nombre character varying NOT NULL,
    logo character varying NOT NULL,
    tipo public.tipoequipo NOT NULL,
    pais character varying NOT NULL,
    confederacion_id integer,
    id integer NOT NULL
);


ALTER TABLE public.equipo OWNER TO postgres;

--
-- Name: equipo_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.equipo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.equipo_id_seq OWNER TO postgres;

--
-- Name: equipo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.equipo_id_seq OWNED BY public.equipo.id;


--
-- Name: estadisticaspartido; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.estadisticaspartido (
    id integer NOT NULL,
    partido_id integer NOT NULL,
    posesion_local integer NOT NULL,
    posesion_visitante integer NOT NULL,
    tiros_puerta_local integer NOT NULL,
    tiros_puerta_visitante integer NOT NULL
);


ALTER TABLE public.estadisticaspartido OWNER TO postgres;

--
-- Name: estadisticaspartido_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.estadisticaspartido_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.estadisticaspartido_id_seq OWNER TO postgres;

--
-- Name: estadisticaspartido_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.estadisticaspartido_id_seq OWNED BY public.estadisticaspartido.id;


--
-- Name: participacion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.participacion (
    equipo_id integer NOT NULL,
    competicion_id integer NOT NULL
);


ALTER TABLE public.participacion OWNER TO postgres;

--
-- Name: partido; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.partido (
    competicion_id integer,
    equipo_local_id integer,
    equipo_visitante_id integer,
    marcador_local integer NOT NULL,
    marcador_visitante integer NOT NULL,
    estado public.estadopartido NOT NULL,
    id integer NOT NULL
);


ALTER TABLE public.partido OWNER TO postgres;

--
-- Name: partido_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.partido_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.partido_id_seq OWNER TO postgres;

--
-- Name: partido_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.partido_id_seq OWNED BY public.partido.id;


--
-- Name: competicion id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.competicion ALTER COLUMN id SET DEFAULT nextval('public.competicion_id_seq'::regclass);


--
-- Name: confederacion id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.confederacion ALTER COLUMN id SET DEFAULT nextval('public.confederacion_id_seq'::regclass);


--
-- Name: equipo id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipo ALTER COLUMN id SET DEFAULT nextval('public.equipo_id_seq'::regclass);


--
-- Name: estadisticaspartido id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estadisticaspartido ALTER COLUMN id SET DEFAULT nextval('public.estadisticaspartido_id_seq'::regclass);


--
-- Name: partido id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.partido ALTER COLUMN id SET DEFAULT nextval('public.partido_id_seq'::regclass);


--
-- Data for Name: competicion; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.competicion (nombre, logo, tipo, pais, confederacion_id, id) FROM stdin;
Liga BetPlay	https://static.wikia.nocookie.net/logopedia/images/7/7f/LigaBetPlay.png/revision/latest?cb=20210410195804&path-prefix=es	LIGA_NACIONAL	Colombia	1	1
UEFA Champions League	https://upload.wikimedia.org/wikipedia/commons/e/e2/UEFA_Champions_League_logo.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original	INTERNACIONAL_CLUBES	Internacional	2	2
Copa Mundial de la FIFA	https://thumb.wikimedia.org/wikipedia/en/thumb/1/17/2026_FIFA_World_Cup_emblem.svg/960px-2026_FIFA_World_Cup_emblem.svg.png?utm_source=en.wikipedia.org&utm_campaign=index&utm_content=thumbnail	INTERNACIONAL_SELECCIONES	Internacional	\N	3
\.


--
-- Data for Name: confederacion; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.confederacion (nombre, logo, id) FROM stdin;
CONMEBOL	https://static.wikia.nocookie.net/youtubepedia/images/a/ab/Conmebol.png/revision/latest/thumbnail/width/360/height/360?cb=20200315193455&path-prefix=es	1
UEFA	https://img.uefa.com/imgml/uefaorg/new/logo.png	2
\.


--
-- Data for Name: equipo; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.equipo (nombre, logo, tipo, pais, confederacion_id, id) FROM stdin;
Real Madrid	https://upload.wikimedia.org/wikipedia/en/5/56/Real_Madrid_CF.svg	CLUB	España	2	2
Colombia	https://upload.wikimedia.org/wikipedia/commons/2/21/Flag_of_Colombia.svg	SELECCION	Colombia	1	3
Deportes Tolima	https://upload.wikimedia.org/wikipedia/commons/4/4a/Escudo_del_Deportes_Tolima.svg?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original	CLUB	Colombia	1	1
\.


--
-- Data for Name: estadisticaspartido; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.estadisticaspartido (id, partido_id, posesion_local, posesion_visitante, tiros_puerta_local, tiros_puerta_visitante) FROM stdin;
\.


--
-- Data for Name: participacion; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.participacion (equipo_id, competicion_id) FROM stdin;
1	1
2	2
3	3
\.


--
-- Data for Name: partido; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.partido (competicion_id, equipo_local_id, equipo_visitante_id, marcador_local, marcador_visitante, estado, id) FROM stdin;
\.


--
-- Name: competicion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.competicion_id_seq', 3, true);


--
-- Name: confederacion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.confederacion_id_seq', 2, true);


--
-- Name: equipo_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.equipo_id_seq', 3, true);


--
-- Name: estadisticaspartido_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.estadisticaspartido_id_seq', 1, false);


--
-- Name: partido_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.partido_id_seq', 1, false);


--
-- Name: competicion competicion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.competicion
    ADD CONSTRAINT competicion_pkey PRIMARY KEY (id);


--
-- Name: confederacion confederacion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.confederacion
    ADD CONSTRAINT confederacion_pkey PRIMARY KEY (id);


--
-- Name: equipo equipo_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipo
    ADD CONSTRAINT equipo_pkey PRIMARY KEY (id);


--
-- Name: estadisticaspartido estadisticaspartido_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estadisticaspartido
    ADD CONSTRAINT estadisticaspartido_pkey PRIMARY KEY (id);


--
-- Name: participacion participacion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participacion
    ADD CONSTRAINT participacion_pkey PRIMARY KEY (equipo_id, competicion_id);


--
-- Name: partido partido_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.partido
    ADD CONSTRAINT partido_pkey PRIMARY KEY (id);


--
-- Name: ix_confederacion_nombre; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_confederacion_nombre ON public.confederacion USING btree (nombre);


--
-- Name: competicion competicion_confederacion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.competicion
    ADD CONSTRAINT competicion_confederacion_id_fkey FOREIGN KEY (confederacion_id) REFERENCES public.confederacion(id);


--
-- Name: equipo equipo_confederacion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.equipo
    ADD CONSTRAINT equipo_confederacion_id_fkey FOREIGN KEY (confederacion_id) REFERENCES public.confederacion(id);


--
-- Name: estadisticaspartido estadisticaspartido_partido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estadisticaspartido
    ADD CONSTRAINT estadisticaspartido_partido_id_fkey FOREIGN KEY (partido_id) REFERENCES public.partido(id);


--
-- Name: participacion participacion_competicion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participacion
    ADD CONSTRAINT participacion_competicion_id_fkey FOREIGN KEY (competicion_id) REFERENCES public.competicion(id);


--
-- Name: participacion participacion_equipo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.participacion
    ADD CONSTRAINT participacion_equipo_id_fkey FOREIGN KEY (equipo_id) REFERENCES public.equipo(id);


--
-- Name: partido partido_competicion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.partido
    ADD CONSTRAINT partido_competicion_id_fkey FOREIGN KEY (competicion_id) REFERENCES public.competicion(id);


--
-- Name: partido partido_equipo_local_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.partido
    ADD CONSTRAINT partido_equipo_local_id_fkey FOREIGN KEY (equipo_local_id) REFERENCES public.equipo(id);


--
-- Name: partido partido_equipo_visitante_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.partido
    ADD CONSTRAINT partido_equipo_visitante_id_fkey FOREIGN KEY (equipo_visitante_id) REFERENCES public.equipo(id);


--
-- PostgreSQL database dump complete
--

\unrestrict f4V0kXucJLOUGJyQnp4hdQ1MzDy7bPa9db41kwkQFlrUTBeU874DKOewn1gRujO

