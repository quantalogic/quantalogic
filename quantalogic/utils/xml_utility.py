import re
from typing import List, Type, TypeVar

from lxml import etree
from pydantic import BaseModel, Field

# Type variable for Pydantic model compatibility
T = TypeVar("T", bound=BaseModel)


def get_localname(tag: str) -> str:
    """
    Extract the local name from a namespaced tag.

    Args:
        tag: The tag name, potentially with a namespace (e.g., '{http://example.com}name').

    Returns:
        The tag’s local name (e.g., 'name').
    """
    return re.sub(r"^\{.*\}", "", tag)


def element_to_dict(element):
    """
    Recursively convert an XML element to a dictionary for Pydantic parsing.

    Args:
        element: An lxml.etree.Element object.

    Returns:
        A dictionary representing the element’s structure.
        - Attributes use '@' prefix (e.g., '@id').
        - Text content (including CDATA) is stored as '#text'.
        - Repeated tags become lists.
    """
    result = {}

    # Capture attributes with '@' prefix
    if element.attrib:
        for key, value in element.attrib.items():
            result[f"@{get_localname(key)}"] = value

    # Handle text content (including CDATA) if present
    if element.text and element.text.strip():
        result["#text"] = element.text.strip()

    # Process child elements
    for child in element:
        child_dict = element_to_dict(child)
        local_tag = get_localname(child.tag)

        if local_tag in result:
            # Convert to list for repeated tags
            if not isinstance(result[local_tag], list):
                result[local_tag] = [result[local_tag]]
            result[local_tag].append(child_dict)
        else:
            result[local_tag] = child_dict

    # For simple leaf elements with no children, attributes or just text content
    # This optimization avoids unnecessary nesting but preserves structure for complex types
    if (
        len(element) == 0
        and not element.attrib
        and len(result) == 1
        and "#text" in result
        and
        # Don't simplify these elements, they should remain as dictionaries
        get_localname(element.tag) not in ["description"]
    ):
        return result["#text"]

    return result


def parse_xml_to_model(xml_content: str, model: Type[T]) -> T:
    """
    Parse XML content into a Pydantic V2 model instance with fault tolerance.

    Args:
        xml_content: A string of XML data.
        model: The Pydantic model class to instantiate.

    Returns:
        An instance of the specified Pydantic model, using defaults for missing fields.

    Raises:
        etree.XMLSyntaxError: If XML parsing fails despite recovery attempts.
        pydantic.ValidationError: If data doesn’t match the model (after defaults).
    """
    # Parse XML with fault-tolerant settings
    parser = etree.XMLParser(recover=True)
    root = etree.fromstring(xml_content, parser=parser)
    # Convert to dictionary
    data = element_to_dict(root)
    # Validate and create Pydantic model instance, applying defaults
    return model.model_validate(data)


# Test Models with Default Values
class Person(BaseModel):
    name: str = "Unnamed"  # Default value for missing name
    age: int = 0  # Default value for missing age


class Description(BaseModel):
    content: str = Field(default="No description", alias="#text")
    type: str = Field(default="unknown", alias="@type")


class Item(BaseModel):
    description: Description = Field(default_factory=lambda: Description(content="Default content", type="default"))


class People(BaseModel):
    person: List[Person] = Field(default_factory=lambda: [Person(name="Default Person", age=99)])


def main():
    """Run example tests to demonstrate XML parsing with Pydantic default values."""
    # Test 1: Simple XML with all fields present
    print("Test 1: Simple XML (all fields present)")
    xml1 = """
    <person>
        <name>John</name>
        <age>30</age>
    </person>
    """
    person = parse_xml_to_model(xml1, Person)
    print(f"Result: {person}")

    # Test 2: Missing element (use default for age)
    print("\nTest 2: Missing element (default age)")
    xml2 = """
    <person>
        <name>Jane</name>
    </person>
    """
    person = parse_xml_to_model(xml2, Person)
    print(f"Result: {person}")

    # Test 3: Attributes and CDATA with missing attribute
    print("\nTest 3: Missing attribute (default type)")
    xml3 = """
    <item>
        <description><![CDATA[This is text]]></description>
    </item>
    """
    item = parse_xml_to_model(xml3, Item)
    print(f"Result: {item}")

    # Test 4: Empty XML (use default for nested object)
    print("\nTest 4: Empty XML (default Item)")
    xml4 = "<item></item>"
    item = parse_xml_to_model(xml4, Item)
    print(f"Result: {item}")

    # Test 5: Repeated elements with partial data
    print("\nTest 5: Repeated elements (partial data)")
    xml5 = """
    <people>
        <person><name>John</name></person>
        <person><age>25</age></person>
    </people>
    """
    people = parse_xml_to_model(xml5, People)
    print(f"Result: {people}")

    # Test 6: Completely empty root (use default list)
    print("\nTest 6: Empty root (default People)")
    xml6 = "<people></people>"
    people = parse_xml_to_model(xml6, People)
    print(f"Result: {people}")


if __name__ == "__main__":
    main()
