import typer

app = typer.Typer(
    name="voyageur",
    help="Sailing route planner for the Norman coast.",
    no_args_is_help=True,
)


@app.command()
def plan(
    from_port: str = typer.Option(..., "--from", help="Departure port or lat/lon"),
    to_port: str = typer.Option(..., "--to", help="Destination port or lat/lon"),
    depart: str = typer.Option(..., "--depart", help="Departure time (ISO 8601)"),
    wind: str = typer.Option(..., "--wind", help="Wind direction/speed (e.g. 240/15)"),
    step: int = typer.Option(15, "--step", help="Time step in minutes (1,5,15,30,60)"),
) -> None:
    """Plan a sailing passage between two Norman coast ports."""
    typer.echo("Voyage planning not yet implemented.")
