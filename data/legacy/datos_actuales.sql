--
-- PostgreSQL database dump
--

\restrict Rcod18bliRalByaRIGymi2mJUzspgDgbZAxdVFiOH9cDqlbB1THF8jVgHEqwNvK

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

--
-- Data for Name: confederacion; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.confederacion VALUES ('CONMEBOL', 'https://static.wikia.nocookie.net/youtubepedia/images/a/ab/Conmebol.png/revision/latest/thumbnail/width/360/height/360?cb=20200315193455&path-prefix=es', 1);
INSERT INTO public.confederacion VALUES ('UEFA', 'https://img.uefa.com/imgml/uefaorg/new/logo.png', 2);


--
-- Data for Name: competicion; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.competicion VALUES ('UEFA Champions League', 'https://upload.wikimedia.org/wikipedia/commons/e/e2/UEFA_Champions_League_logo.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original', 'INTERNACIONAL_CLUBES', 'Internacional', 2, 2);
INSERT INTO public.competicion VALUES ('Liga BetPlay', 'https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e0/BetPlay-Dimayor_logo.svg/1920px-BetPlay-Dimayor_logo.svg.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=thumbnail', 'LIGA_NACIONAL', 'Colombia', 1, 1);
INSERT INTO public.competicion VALUES ('Copa Mundial de la FIFA', 'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/aa/FIFA_logo_without_slogan.svg/1280px-FIFA_logo_without_slogan.svg.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=thumbnail', 'INTERNACIONAL_SELECCIONES', 'Internacional', 1, 3);


--
-- Data for Name: equipo; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.equipo VALUES ('Real Madrid', 'https://upload.wikimedia.org/wikipedia/en/5/56/Real_Madrid_CF.svg', 'CLUB', 'España', 2, 2);
INSERT INTO public.equipo VALUES ('Colombia', 'https://upload.wikimedia.org/wikipedia/commons/2/21/Flag_of_Colombia.svg', 'SELECCION', 'Colombia', 1, 3);
INSERT INTO public.equipo VALUES ('Deportes Tolima', 'https://upload.wikimedia.org/wikipedia/commons/4/4a/Escudo_del_Deportes_Tolima.svg?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original', 'CLUB', 'Colombia', 1, 1);


--
-- Data for Name: partido; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- Data for Name: estadisticaspartido; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- Data for Name: participacion; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.participacion VALUES (1, 1);
INSERT INTO public.participacion VALUES (2, 2);
INSERT INTO public.participacion VALUES (3, 3);


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
-- PostgreSQL database dump complete
--

\unrestrict Rcod18bliRalByaRIGymi2mJUzspgDgbZAxdVFiOH9cDqlbB1THF8jVgHEqwNvK

