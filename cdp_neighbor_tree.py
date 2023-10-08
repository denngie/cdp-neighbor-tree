#!/usr/bin/python
"""Build a network tree model based on CDP neighbors."""
from re import search
from typing import Optional

# Static data to test
STATIC_DATA = {
    "sweden-pe1.example.com": [
        "norway-pe1.example.com",
        "finland-pe1.example.com",
        "denmark-pe2.example.com",
        "sweden-a1.example.com",
        "sweden-a2.example.com",
        "sweden-a4.example.com",
    ],
    "norway-pe1.example.com": [
        "sweden-pe1.example.com",
        "denmark-pe1.example.com",
        "iceland-pe1.example.com",
    ],
    "finland-pe1.example.com": [
        "sweden-pe1.example.com",
        "greenland-pe1.example.com",
    ],
    "denmark-pe2.example.com": [
        "sweden-pe1.example.com",
        "denmark-a1.example.com",
    ],
    "denmark-a1.example.com": [
        "denmark-pe2.example.com",
    ],
    "sweden-a1.example.com": [
        "sweden-pe1.example.com",
        "sweden-a3.example.com",
        "sweden-a5.example.com",
    ],
    "sweden-a2.example.com": ["sweden-pe1.example.com", "sweden-a6.example.com"],
    "sweden-a3.example.com": ["sweden-a1.example.com", "sweden-a7.example.com"],
    "sweden-a4.example.com": ["sweden-pe1.example.com"],
    "sweden-a5.example.com": ["sweden-a1.example.com"],
    "sweden-a6.example.com": ["sweden-a2.example.com"],
    "sweden-a7.example.com": ["sweden-a3.example.com"],
}

# Regular expression to find P and PE nodes
REGEXP_PE_PATTERN = r"^(?:\w+-)+pe?\d+\."


def split_list_by_regex(lst: list, pattern: str) -> tuple[list[str], list[str]]:
    """Split a list in two parts based on regex match or not"""
    matches = [item for item in lst if search(pattern, item)]
    non_matches = [item for item in lst if not search(pattern, item)]
    return matches, non_matches


class NetworkTreeNode:
    """Standard tree data structure with parent child relationships between nodes"""

    # Keep a dict of existing nodes so we easily can reuse them
    existing_nodes: dict[str, "NetworkTreeNode"] = {}

    def __init__(self, hostname: str):
        self.hostname = hostname
        self.parent: Optional["NetworkTreeNode"] = None
        self.children: list[NetworkTreeNode] = []
        self._add_to_existing()

    def _add_to_existing(self) -> None:
        NetworkTreeNode.existing_nodes[self.hostname] = self

    @classmethod
    def get_existing_node(cls, hostname: str) -> Optional["NetworkTreeNode"]:
        """Get node by hostname if it already exists"""
        return cls.existing_nodes.get(hostname)

    def _add_child(self, child_hostname: str) -> "NetworkTreeNode":
        """Create new child node if needed and set the relationship between the nodes"""
        child = NetworkTreeNode.get_existing_node(child_hostname)
        if child is None:
            child = NetworkTreeNode(child_hostname)

        # Return child node without any modification if the new node is already our parent
        if self.parent == child:
            return child

        child.parent = self
        self.children.append(child)
        return child

    def find_neighbors(self, visited: set | None = None) -> None:
        """Recursive lookup for nested childrens"""
        # Visited set is used to keep track of already visisted nodes so we don't
        # get stuck in a recursive loop bouncing between two neighbors
        if visited is None:
            visited = set()
        if self in visited:
            return

        # Get CDP neighbors for current node
        cdp_neighbors = STATIC_DATA[self.hostname]

        # Split the neighbor list in two parts, MPLs nodes and dependant nodes
        mpls_neighbors, dependant_neighbors = split_list_by_regex(
            cdp_neighbors, REGEXP_PE_PATTERN
        )

        # Only check for PE redundancy if current node is an P or PE node
        if search(REGEXP_PE_PATTERN, self.hostname):
            # For each MPLS node neighbor, add it as dependant if it
            # does not have at least two MPLS node neighbors
            for neighbor in mpls_neighbors:
                cdp_neighbors = STATIC_DATA[neighbor]
                mpls_neighbors, _ = split_list_by_regex(
                    cdp_neighbors, REGEXP_PE_PATTERN
                )

                if len(mpls_neighbors) < 2:
                    dependant_neighbors.append(neighbor)

        # For each dependant node neighbor:
        #   - Add them as neighbor
        #   - Add current node as visisted
        #   - Check child node for their neighbors
        for neighbor in dependant_neighbors:
            child_node = self._add_child(neighbor)
            visited.add(self)
            child_node.find_neighbors(visited)

    def _get_level(self) -> int:
        level = 0
        p = self.parent
        while p:
            level += 1
            p = p.parent
        return level

    def print_tree(self) -> None:
        """Pretty print tree"""
        spaces = " " * self._get_level() * 3
        prefix = spaces + "|--" if self.parent else ""
        print(prefix + self.hostname)
        if self.children:
            for child in self.children:
                child.print_tree()


def find_root(hostname: str, visited: set | None = None) -> Optional[str]:
    """Attempt to find first MPLS node neighbor's hostname for the given hostname"""
    # Visited set is used to keep track of already visisted nodes so we don't
    # get stuck in a recursive loop bouncing between two neighbors
    if visited is None:
        visited = set()
    if hostname in visited:
        return None

    # If hostname is a MPLS node, use it
    if search(REGEXP_PE_PATTERN, hostname):
        return hostname

    # Get CDP neighbors for current node
    cdp_neighbors = STATIC_DATA[hostname]

    # For each neighbor:
    #   - If it is a MPLS node, use it
    #   - Add it as visited
    #   - Check their neighbors for a MPLS node
    for neighbor in cdp_neighbors:
        if search(REGEXP_PE_PATTERN, neighbor):
            return neighbor

        visited.add(hostname)
        return find_root(neighbor, visited)

    # Return None if no matches
    return None


def main() -> None:
    """Example tree"""
    target = "sweden-a1.example.com"
    root_hostname = find_root(target)
    if root_hostname:
        node = NetworkTreeNode(root_hostname)
        node.find_neighbors()
        target_node = NetworkTreeNode.get_existing_node(target)
        if target_node:
            target_node.print_tree()


if __name__ == "__main__":
    main()
