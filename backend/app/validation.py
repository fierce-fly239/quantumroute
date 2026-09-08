"""Network validation.

The problem statement lists network validation as a required capability. The
point of this module is not to reject files, it is to explain them: every issue
carries a hint saying what to do about it.
"""

from typing import List

from .models import Network, NodeType, ValidationIssue, ValidationResult


def validate_network(net: Network) -> ValidationResult:
    issues: List[ValidationIssue] = []

    nodes = net.nodes
    depots = [n for n in nodes if n.type == NodeType.DEPOT]
    customers = [n for n in nodes if n.type == NodeType.CUSTOMER]

    # --- structure ---
    if len(depots) == 0:
        issues.append(ValidationIssue(
            severity="error",
            message="No depot in this network.",
            hint='Exactly one node must have "type": "depot". Every route starts and ends there.',
        ))
    elif len(depots) > 1:
        issues.append(ValidationIssue(
            severity="error",
            message=f"Found {len(depots)} depots: {', '.join(d.id for d in depots)}.",
            hint="This model supports a single depot. Mark the others as customers.",
        ))

    if not customers:
        issues.append(ValidationIssue(
            severity="error",
            message="No customer stops to deliver to.",
            hint="Add at least one node with \"type\": \"customer\".",
        ))

    ids = [n.id for n in nodes]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        issues.append(ValidationIssue(
            severity="error",
            message=f"Duplicate node ids: {', '.join(dupes)}.",
            hint="Each node needs a unique id. Routes are described by id, so duplicates are ambiguous.",
        ))

    # --- demands against the fleet ---
    fleet = net.meta.fleet
    for d in depots:
        if d.demand != 0:
            issues.append(ValidationIssue(
                severity="error",
                message=f"Depot '{d.id}' has a demand of {d.demand}.",
                hint="The depot is where goods come from, so its demand must be 0.",
            ))

    oversized = [c for c in customers if c.demand > fleet.capacity]
    if oversized:
        names = ", ".join(f"{c.name} ({c.demand})" for c in oversized[:3])
        issues.append(ValidationIssue(
            severity="error",
            message=f"{len(oversized)} stop(s) demand more than one van can carry ({fleet.capacity}): {names}.",
            hint="No single route can ever serve these. Raise the van capacity or split the stop.",
        ))

    total = sum(c.demand for c in customers)
    capacity = fleet.vehicles * fleet.capacity
    if total > capacity:
        issues.append(ValidationIssue(
            severity="error",
            message=(
                f"Total demand {total} exceeds fleet capacity {capacity} "
                f"({fleet.vehicles} {'van' if fleet.vehicles == 1 else 'vans'} x {fleet.capacity})."
            ),
            hint="Add vans, raise capacity, or remove stops. As it stands the problem has no valid answer.",
        ))
    elif capacity and total / capacity > 0.92:
        issues.append(ValidationIssue(
            severity="warning",
            message=f"Fleet is {total / capacity:.0%} loaded ({total} of {capacity}).",
            hint="Very tight. Vans rarely pack perfectly, so the optimizer may need to leave capacity unused.",
        ))

    # --- geography ---
    if len(nodes) >= 2:
        lats = [n.lat for n in nodes]
        lngs = [n.lng for n in nodes]
        if max(lats) - min(lats) > 2.0 or max(lngs) - min(lngs) > 2.0:
            issues.append(ValidationIssue(
                severity="warning",
                message="Stops are spread over more than 200 km.",
                hint="Check the coordinates. This model assumes deliveries within one city.",
            ))

    if net.meta.node_count != len(nodes):
        issues.append(ValidationIssue(
            severity="warning",
            message=f"Metadata says {net.meta.node_count} nodes but the file has {len(nodes)}.",
            hint="The node list is what gets used. The count is only a label.",
        ))

    return ValidationResult(
        valid=not any(i.severity == "error" for i in issues),
        issues=issues,
    )
