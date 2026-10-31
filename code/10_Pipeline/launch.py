"""CRC PyFluent lifecycle helpers; sessions are always closed by caller."""
import ansys.fluent.core as pyfluent


def start(mode, cores=2):
    if cores < 1 or cores > 16:
        raise ValueError('cores must be 1..16')
    # Fluent's documented 2D Meshing workflow runs in the normal 3D
    # Meshing environment and exports a 2D file for a separate 2D solver.
    dimension = pyfluent.Dimension.THREE if mode == 'meshing' else pyfluent.Dimension.TWO
    return pyfluent.launch_fluent(mode=mode, dimension=dimension,
                                  precision=pyfluent.Precision.DOUBLE,
                                  processor_count=cores, cleanup_on_exit=True,
                                  start_timeout=180)


def close(session):
    if session is not None:
        session.exit()
