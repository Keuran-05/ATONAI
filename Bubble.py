import plotly.express as px
from io import BytesIO
import numpy as np
from scipy.spatial import distance
from Helius import getTokenLargestAccounts
from Logs import log_info, log_warning

def create_packed_bubble_chart(wallet_balances):
    """Create a packed bubble chart for wallet balances with a heat map."""
    log_info("Creating packed bubble chart for wallet balances.")
    addresses, balances = zip(*wallet_balances) if wallet_balances else ([], [])
    data = {"Address": addresses, "Balance": balances}

    # Bubble radii based on balances
    radii = np.sqrt(np.array(balances) / np.pi)

    # Initialize bubble positions (simple force-directed packing algorithm)
    positions = []
    for i, r in enumerate(radii):
        pos = np.array([0.0, 0.0])
        attempts = 0
        while attempts < 1000:  # Prevent infinite loops
            pos = np.random.uniform(-1, 1, size=2) * len(radii) * 10
            if all(distance.euclidean(pos, p) > r + radii[j] for j, p in enumerate(positions)):
                break
            attempts += 1
        positions.append(pos)
    positions = np.array(positions)

    # Create the scatter plot
    fig = px.scatter(
        data,
        x=positions[:, 0],
        y=positions[:, 1],
        size="Balance",
        color="Balance",
        hover_name="Address",
        color_continuous_scale=px.colors.sequential.Purples,
        title="Top Wallets by Token",
    )

    fig.update_layout(
        plot_bgcolor="black",
        paper_bgcolor="black",
        font_color="white",
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )

    fig.update_traces(
        marker=dict(
            sizemode="area",
            sizeref=2. * max(balances) / (100. ** 2) if balances else 1,
            line=dict(width=2, color="white"),
        )
    )

    buffer = BytesIO()
    fig.write_image(buffer, format="png")
    buffer.seek(0)

    log_info("Packed bubble chart created successfully.")
    return buffer


async def run_bubble(token_address: str):
    """Run the bubble chart generation asynchronously."""
    log_info(f"Running bubble chart generation for mint address: {token_address}")
    top_wallets = await getTokenLargestAccounts(token_address)

    if top_wallets:
        log_info(f"Wallet data found: {top_wallets}")
        log_info("Proceeding to create bubble chart.")
        return create_packed_bubble_chart(top_wallets)

    log_warning(f"No wallets found for mint address: {token_address}")
    return None

