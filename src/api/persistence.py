"""Small persistence primitives; each write endpoint owns its transaction."""


def save(session, entity):
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity
