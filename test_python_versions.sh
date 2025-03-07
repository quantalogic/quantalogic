#!/bin/bash

# Initialize pyenv
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

VERSIONS=("3.10.0" "3.11.0" "3.12.0")
PACKAGE="dist/quantalogic-0.55.0-py3-none-any.whl"

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null
then
    echo "pyenv could not be found, please install it first"
    exit 1
fi

# Install required Python versions if not already installed
for version in "${VERSIONS[@]}"
do
    if ! pyenv versions | grep -q $version; then
        echo "Installing Python $version..."
        pyenv install $version
    fi
done

# Create and test in virtual environments
for version in "${VERSIONS[@]}"
do
    env_name="quantalogic-${version//./}"
    echo "Testing with Python $version..."
    
    # Create virtual environment if it doesn't exist
    if ! pyenv versions | grep -q $env_name; then
        pyenv virtualenv $version $env_name
    fi
    
    # Activate environment and test package
    pyenv activate $env_name
    
    # Update pip version
    python -m pip install --upgrade pip==25.0.1
    
    # Install package dependencies first
    pip install -r requirements.txt
    
    # Then install the package
    pip install --force-reinstall $PACKAGE
    
    # Verify installation
    if python -c "import quantalogic; print(f'Successfully imported quantalogic version: {quantalogic.__version__}')"; then
        echo "Package works correctly with Python $version"
    else
        echo "Package import failed with Python $version"
    fi
    
    pyenv deactivate
    
    echo -e "Python $version test complete\n"
done

echo "All versions tested successfully!"
