# Copilot Instructions

Please use this slightly modified guide to google style docstrings as reference for kalbio documentation.

## Notes To Follow

### Temporary

- For now, ensure that whenever a method has an identifier type as an arguement, a statement like
  "Any type of RecordIdentifier will be accepted and resolved"
  will be attached. An example is provided.

  ````python
  def get_record_by_id(self, record_id: RecordIdentifier) -> Record | None:
      """Retrieves a record by its identifier.

      Args:
          record_id: The identifier of the record to retrieve.
              Any type of RecordIdentifier will be accepted and resolved

      Returns:
          The record object if found, otherwise None.

      Example:
          ```python
          record = client.records.get_record_by_id("record_uuid")
          print(record.record_identifier if record else "missing")
          ```
      """
      # continued ...
  ````

### General

- Use google style documentation on kalbio
- Avoid making unneeded, verbose documentation.
- Ensure that every public field is documented. Only document module-private and private fields if they contain noteable behaviour.
- Ensure every piece of documentation is up-to-date with the latest syntax. Do not assume that existing documentation is correct and up-to-date.
- Ensure that there are no typos.

### Documentation Guidelines

- Every module should have a thorough explanation of it's functionality and purpose.
- Every class should be documented
- Methods that define any type of property (i.e. methods with the @property or @cached_property) should only be documented if they contain noteable behaviour.
- In a method's docstring, do not specify argument types or return type if the method already contains type annotation. Remove this type description if seen.

  - For example do this:

    ```python
    def example_1(param_1: int) -> str:
    """Short description

    Long description

    Args:
        param_1: parameter description

    Returns:
        Return value description
    """
        pass
    ```

  - Rather than:

    ```python
    def example_1(param_1: int) -> str:
    """Short description

    Long description

    Args:
        param_1 (int): parameter description

    Returns:
        str: Return value description
    """
        pass
    ```

- Every method should have type annotation. The return type does not need to be annotated if the return type is None.

### Example Guidelines

- All examples are written in block code format. Do not write doctest formatted examples.
- Every class apart from Enums should have an example.
- Every method should have an example.
- However, methods that are any type of property (i.e. methods with the @property or @cached_property) should only be documented if they contain any noteable behaviour.
- Services in `kalbio` are called as attributes from one client instance. When writing examples, don't make an instance of a service and pass in a client. Look at this example instead:

  ```python
  """
  Example for using `KaleidoscopeClient`
  """

  from kalbio.client import KaleidoscopeClient

  # initialize client
  client = KaleidoscopeClient()

  # fetch activities
  activities = client.activities.get_activities()

  # print to console
  print(activities)
  ```

## Google Style Documentation

The below blockcode should serve as the major reference to making proper google style documentation.

The source came from [here](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html).

````python
"""Example Google style docstrings.

This module demonstrates documentation as specified by the `Google Python
Style Guide`_. Docstrings may extend over multiple lines. Sections are created
with a section header and a colon followed by a block of indented text.

Example:
    Examples can be given using either the ``Example`` or ``Examples``
    sections. Module and class examples should be valid block code written like

    ```python
    # pass
    # examples follow here
    # the below bracket should have 3 backticks, not two
    ``

Section breaks are created by resuming unindented text. Section breaks
are also implicitly created anytime a new section starts.

Attributes:
    module_level_variable1 (int): Module level variables may be documented in
        either the ``Attributes`` section of the module docstring, or in an
        inline docstring immediately following the variable.

        Either form is acceptable, but the two should not be mixed. Choose
        one convention to document module level variables and be consistent
        with it.

Todo:
    * For module TODOs
    * You have to also use ``sphinx.ext.todo`` extension
"""

# Make the need imports to typing here
from typing import Any

module_level_variable: int = 98765
"""Module level variable documented inline.

The docstring may span multiple lines. When there is not a type annotation,
the type may optionally be specified on the first line, separated by a colon.
"""


def function_with_pep484_type_annotations(param1: int, param2: str) -> bool:
    """Example function with PEP 484 type annotations.

    Ideally, every method in kalbio should be in this format.

    Args:
        param1: The first parameter.
        param2: The second parameter.

    Returns:
        The return value. True for success, False otherwise.

    """


def module_level_function(param1: int, param2: str | None = None, *args, **kwargs) -> bool:
    """This is an example of a module level function.

    Function parameters should be documented in the ``Args`` section. The name
    of each parameter is required. The type and description of each parameter
    is optional, but should be included if not obvious.

    If \*args or \*\*kwargs are accepted,
    they should be listed as ``*args`` and ``**kwargs``.

    The format for a parameter is::

        name (type): description
            The description may span multiple lines. Following
            lines should be indented. The "(type)" is optional.

            The "(type)" documentatino should never be included in kalbio if the function has type annotations

            Multiple paragraphs are supported in parameter
            descriptions.

    Args:
        param1: The first parameter.
        param2: The second parameter. Defaults to None.
            Second line of description should be indented.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        True if successful, False otherwise.

        The return type is optional and may be specified at the beginning of
        the ``Returns`` section followed by a colon.

        The ``Returns`` section may span multiple lines and paragraphs.
        Following lines should be indented to match the first line.

        The ``Returns`` section supports any reStructuredText formatting,
        including literal blocks::

            {
                'param1': param1,
                'param2': param2
            }

    Raises:
        AttributeError: The ``Raises`` section is a list of all exceptions
            that are relevant to the interface.
        ValueError: If `param2` is equal to `param1`.

    """
    if param1 == param2:
        raise ValueError('param1 may not be equal to param2')
    return True


def example_generator(n: int) -> Generator[int]:
    """Generators have a ``Yields`` section instead of a ``Returns`` section.

    Args:
        n (int): The upper limit of the range to generate, from 0 to `n` - 1.

    Yields:
        The next number in the range of 0 to `n` - 1.

    Examples:
        Examples should illustrate how
        to use the function.

        ```python
        print([i for i in example_generator(4)])
        # [0, 1, 2, 3]
        # the below bracket should have 3 backticks, not two
        ``

    """
    for i in range(n):
        yield i


class ExampleError(Exception):
    """Exceptions are documented in the same way as classes.

    The __init__ method may be documented in either the class level
    docstring, or as a docstring on the __init__ method itself.

    Either form is acceptable, but the two should not be mixed. Choose one
    convention to document the __init__ method and be consistent with it.

    Note:
        Do not include the `self` parameter in the ``Args`` section.

    Args:
        msg (str): Human readable string describing the exception.
        code (:obj:`int`, optional): Error code.

    Attributes:
        msg (str): Human readable string describing the exception.
        code (int): Exception error code.

    """

    def __init__(self, msg, code):
        self.msg = msg
        self.code = code


class ExampleClass(object):
    """The summary line for a class docstring should fit on one line.

    If the class has public attributes, they may be documented here
    in an ``Attributes`` section and follow the same formatting as a
    function's ``Args`` section. Alternatively, attributes may be documented
    inline with the attribute's declaration (see __init__ method below).

    Properties created with the ``@property`` decorator should be documented
    in the property's getter method.

    Attributes:
        attr1 (str): Description of `attr1`.
        attr2 (:obj:`int`, optional): Description of `attr2`.

    """

    def __init__(self, param1: str, param2: int, param3: list[str]):
        """Example of docstring on the __init__ method.

        The __init__ method may be documented in either the class level
        docstring, or as a docstring on the __init__ method itself.

        In kalbio, document on the __init__ method itself.

        Note:
            Do not include the `self` parameter in the ``Args`` section.

        Args:
            param1: Description of `param1`.
            param2: Description of `param2`. Multiple
                lines are supported.
            param3: Description of `param3`.

        """
        self.attr1 = param1
        self.attr2 = param2
        self.attr3 = param3  #: Doc comment *inline* with attribute

        # Doc comment *before* attribute, with type specified
        self.attr4: list[str] = ['attr4']

        self.attr5: str | None = None
        """Docstring *after* attribute, with type specified."""

    @property
    def readonly_property(self) -> str:
        """Properties should be documented in their getter method."""
        return 'readonly_property'

    @property
    def readwrite_property(self) -> list[str]:
        """Properties with both a getter and setter
        should only be documented in their getter method.

        If the setter method contains notable behavior, it should be
        mentioned here.
        """
        return ['readwrite_property']

    @readwrite_property.setter
    def readwrite_property(self, value: Any):
        """Example setter method."""
        pass

    def example_method(self, param1: Any, param2: Any) -> bool:
        """Class methods are similar to regular functions.

        Note:
            Do not include the `self` parameter in the ``Args`` section.

        Args:
            param1: The first parameter.
            param2: The second parameter.

        Returns:
            True if successful, False otherwise.

        """
        return True

    def __special__(self):
        """By default special members with docstrings are not included.

        Special members are any methods or attributes that start with and
        end with a double underscore. Any special member with a docstring
        will be included in the output, if
        ``napoleon_include_special_with_doc`` is set to True.

        This behavior can be enabled by changing the following setting in
        Sphinx's conf.py::

            napoleon_include_special_with_doc = True

        """
        pass

    def __special_without_docstring__(self):
        pass

    def _private(self):
        """By default private members are not included.

        Private members are any methods or attributes that start with an
        underscore and are *not* special. By default they are not included
        in the output.

        This behavior can be changed such that private members *are* included
        by changing the following setting in Sphinx's conf.py::

            napoleon_include_private_with_doc = True

        """
        pass

    def _private_without_docstring(self):
        pass
````
