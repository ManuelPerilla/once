from sqlmodel import Session, select
from src.models import Confederacion, Competicion, Equipo, TipoCompeticion, TipoEquipo

def ejecutar_seed(session: Session):
    # Verificamos si ya existen datos para evitar duplicados
    existentes = session.exec(select(Confederacion)).first()
    if existentes:
        print("🌱 [VÉRTICE] La base de datos ya contiene datos maestros. Omitiendo seed.")
        return

    print("🚀 [VÉRTICE] Base de datos vacía detectada. Sembrando datos maestros exactos...")

    # 1. CONFEDERACIONES[cite: 1]
    conmebol = Confederacion(
        nombre="CONMEBOL",
        logo="https://static.wikia.nocookie.net/youtubepedia/images/a/ab/Conmebol.png/revision/latest/thumbnail/width/360/height/360?cb=20200315193455&path-prefix=es"
    )
    uefa = Confederacion(
        nombre="UEFA",
        logo="https://img.uefa.com/imgml/uefaorg/new/logo.png"
    )
    session.add_all([conmebol, uefa])
    session.commit()
    session.refresh(conmebol)
    session.refresh(uefa)

    # 2. COMPETICIONES[cite: 1]
    champions = Competicion(
        nombre="UEFA Champions League",
        logo="https://upload.wikimedia.org/wikipedia/commons/e/e2/UEFA_Champions_League_logo.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original",
        tipo=TipoCompeticion.INTERNACIONAL_CLUBES,
        pais="Internacional",
        confederacion_id=uefa.id
    )
    liga_colombiana = Competicion(
        nombre="Liga BetPlay",
        logo="https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e0/BetPlay-Dimayor_logo.svg/1920px-BetPlay-Dimayor_logo.svg.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
        tipo=TipoCompeticion.LIGA_NACIONAL,
        pais="Colombia",
        confederacion_id=conmebol.id
    )
    mundial = Competicion(
        nombre="Copa Mundial de la FIFA",
        logo="https://thumb.wikimedia.org/wikipedia/commons/thumb/a/aa/FIFA_logo_without_slogan.svg/1280px-FIFA_logo_without_slogan.svg.png?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=thumbnail",
        tipo=TipoCompeticion.INTERNACIONAL_SELECCIONES,
        pais="Internacional",
        confederacion_id=conmebol.id
    )

    session.add_all([champions, liga_colombiana, mundial])
    session.commit()
    session.refresh(champions)
    session.refresh(liga_colombiana)
    session.refresh(mundial)

    # 3. EQUIPOS[cite: 1]
    tolima = Equipo(
        nombre="Deportes Tolima",
        logo="https://upload.wikimedia.org/wikipedia/commons/4/4a/Escudo_del_Deportes_Tolima.svg?utm_source=es.wikipedia.org&utm_campaign=index&utm_content=original",
        tipo=TipoEquipo.CLUB,
        pais="Colombia",
        confederacion_id=conmebol.id
    )
    real_madrid = Equipo(
        nombre="Real Madrid",
        logo="https://upload.wikimedia.org/wikipedia/en/5/56/Real_Madrid_CF.svg",
        tipo=TipoEquipo.CLUB,
        pais="España",
        confederacion_id=uefa.id
    )
    colombia = Equipo(
        nombre="Colombia",
        logo="https://upload.wikimedia.org/wikipedia/commons/2/21/Flag_of_Colombia.svg",
        tipo=TipoEquipo.SELECCION,
        pais="Colombia",
        confederacion_id=conmebol.id
    )

    session.add_all([tolima, real_madrid, colombia])
    session.commit()
    session.refresh(tolima)
    session.refresh(real_madrid)
    session.refresh(colombia)

    # 4. MATRÍCULAS / PARTICIPACIONES[cite: 1]
    # Deportes Tolima (1) en Liga BetPlay (1)[cite: 1]
    tolima.competiciones.append(liga_colombiana)
    # Real Madrid (2) en UEFA Champions League (2)[cite: 1]
    real_madrid.competiciones.append(champions)
    # Colombia (3) en Copa Mundial de la FIFA (3)[cite: 1]
    colombia.competiciones.append(mundial)

    session.add_all([tolima, real_madrid, colombia])
    session.commit()

    print("✨ [VÉRTICE] Semilla ejecutada con éxito. Datos maestros sincronizados desde la base de datos.")