# Project Setup

## Setting up the Python Virtual Environment

1. **Install Python**: Ensure that you have Python installed on your system. You can download it from [python.org](https://www.python.org/).

2. **Create a Virtual Environment**:
    - Open your terminal or command prompt.
    - Navigate to the project directory.
    - Run the following command to create a virtual environment:
      ```bash
      python -m venv venv
      ```
    - This will create a directory named `venv` in your project folder.

3. **Activate the Virtual Environment**:
    - **Windows**:
      ```bash
      venv\Scripts\activate
      ```
    - **macOS and Linux**:
      ```bash
      source venv/bin/activate
      ```

## Installing Requirements

Once the virtual environment is activated, install the required packages using `pip`:

```bash
pip install -r requirements.txt
```

This command will read the `requirements.txt` file and install the necessary dependencies listed in it.

## Running the Script

To run the script, ensure your virtual environment is activated and execute the following command:

```bash
python simulator.py
```

This will start the simulator, and you can use the GUI to interact with the controls.
