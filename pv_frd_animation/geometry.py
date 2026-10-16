"""Choose a real interior mesh location for a fly-through of the moving beam."""


def fly_through_target(pv, reader):
    from vtkmodules.vtkCommonCore import reference
    from vtkmodules.vtkCommonDataModel import vtkCellLocator

    grid = pv.servermanager.Fetch(reader)
    bounds = grid.GetBounds()
    center = [(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)]
    locator = vtkCellLocator()
    locator.SetDataSet(grid)
    locator.BuildLocator()
    closest = [0.0]*3
    cell_id, sub_id, distance = reference(0), reference(0), reference(0.0)
    locator.FindClosestPoint(center, closest, cell_id, sub_id, distance)
    cell = grid.GetCell(int(cell_id))
    if cell.GetCellDimension() != 3:
        raise RuntimeError('Fly-through needs a volume mesh with 3D cells')
    pcoords, point = [0.0]*3, [0.0]*3
    sub_id = reference(cell.GetParametricCenter(pcoords))
    weights = [0.0]*cell.GetNumberOfPoints()
    cell.EvaluateLocation(sub_id, pcoords, point, weights)
    vectors = grid.GetPointData().GetArray('disp')
    displacement = [sum(weights[j]*vectors.GetComponent(cell.GetPointId(j), i)
                        for j in range(cell.GetNumberOfPoints())) for i in range(3)]
    return dict(point=point, disp=displacement, cell_id=int(cell_id))
