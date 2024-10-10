import os
import json
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

console = Console()

# Helper function to count files in a directory
def count_files_in_directory(directory):
    try:
        return len([name for name in os.listdir(directory) if os.path.isfile(os.path.join(directory, name))])
    except FileNotFoundError:
        return 0

# Function to calculate dashboard statistics
def calculate_dashboard_stats(base_dir):
    stats = {
        'total_experiments': 0,
        'total_files': 0,
        'logs': 0,
        'responses': 0,
        'saved_context_cycles': 0,
    }

    experiment_folders = [f for f in os.listdir(base_dir) if f.startswith("experiment_")]
    stats['total_experiments'] = len(experiment_folders)

    for folder in experiment_folders:
        experiment_dir = os.path.join(base_dir, folder)
        
        # Count total files in the 'files' folder
        stats['total_files'] += count_files_in_directory(os.path.join(experiment_dir, 'files'))

        # Count files in the 'logs' folder
        stats['logs'] += count_files_in_directory(os.path.join(experiment_dir, 'logs'))

        # Count files in the 'responses' folder
        stats['responses'] += count_files_in_directory(os.path.join(experiment_dir, 'responses'))

        # Count cycles in 'saved_context' (i.e., folders inside saved_context)
        saved_context_dir = os.path.join(experiment_dir, 'saved_context')
        if os.path.exists(saved_context_dir):
            projects = os.listdir(saved_context_dir)
            for project in projects:
                project_dir = os.path.join(saved_context_dir, project)
                if os.path.isdir(project_dir):
                    stats['saved_context_cycles'] += len([f for f in os.listdir(project_dir) if f.startswith('cycle')])

    return stats

# Function to display the dashboard statistics
def show_dashboard(base_dir):
    stats = calculate_dashboard_stats(base_dir)

    table = Table(title="Experiment Dashboard")
    table.add_column("Metric", justify="left", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="magenta")

    table.add_row("Total experiments", str(stats['total_experiments']))
    table.add_row("Total files in 'files' folders", str(stats['total_files']))
    table.add_row("Total log files", str(stats['logs']))
    table.add_row("Total response files", str(stats['responses']))
    table.add_row("Total saved context cycles", str(stats['saved_context_cycles']))

    console.print(table)

    console.print("\n[bold green]Press 'Enter' to continue to experiment explorer.[/bold green]")
    input()

# Function to explore experiments and display basic statistics
def explore_experiments(base_dir):
    experiment_folders = [f for f in os.listdir(base_dir) if f.startswith("experiment_")]

    while True:
        console.clear()
        table = Table(title="Experiment Explorer")
        table.add_column("Index", justify="right", style="cyan", no_wrap=True)
        table.add_column("Experiment Folder", justify="left", style="magenta")

        for idx, folder in enumerate(experiment_folders):
            table.add_row(str(idx + 1), folder)

        console.print(table)

        experiment_choice = Prompt.ask("\nEnter the index of an experiment to view details (or 'q' to quit)", default="q")

        if experiment_choice == 'q':
            break

        try:
            experiment_idx = int(experiment_choice) - 1
            if 0 <= experiment_idx < len(experiment_folders):
                show_experiment_details(base_dir, experiment_folders[experiment_idx])
            else:
                console.print("[bold red]Invalid index, please try again.[/bold red]")
        except ValueError:
            console.print("[bold red]Invalid input, please enter a number.[/bold red]")

# Function to show detailed information about an experiment
def show_experiment_details(base_dir, experiment_folder):
    experiment_dir = os.path.join(base_dir, experiment_folder)
    subfolders = ['files', 'logs', 'responses', 'saved_context']

    table = Table(title=f"Details for {experiment_folder}")
    table.add_column("Subfolder", justify="left", style="cyan", no_wrap=True)
    table.add_column("File Count", justify="right", style="magenta")
    table.add_column("Analysis", justify="left", style="green")

    for subfolder in subfolders:
        subfolder_path = os.path.join(experiment_dir, subfolder)
        file_count = count_files_in_directory(subfolder_path)
        analysis_placeholder = "[Placeholder]"

        if subfolder == 'logs':
            analysis_placeholder = "[Log analysis placeholder]"
        elif subfolder == 'responses':
            analysis_placeholder = "[Response analysis placeholder]"
        elif subfolder == 'saved_context':
            analysis_placeholder = "[Context cycle analysis placeholder]"

        table.add_row(subfolder, str(file_count), analysis_placeholder)

    console.print(table)
    console.print("\n[bold green]Press 'b' to go back.[/bold green]")
    while True:
        key = input()
        if key.lower() == 'b':
            break

# Main function to run the program
def main():
    base_dir = "experimental_setups"  # Adjust if needed
    if not os.path.exists(base_dir):
        console.print(f"[bold red]Error: Base directory '{base_dir}' does not exist.[/bold red]")
        return

    # Show dashboard and experiment explorer
    show_dashboard(base_dir)
    explore_experiments(base_dir)

if __name__ == "__main__":
    main()