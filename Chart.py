from datetime import datetime
import time
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, MaxNLocator
from io import BytesIO
from Solscan import get_price


async def get_chart(token_address):
    now = int(time.time())
    last_week = now - (7 * 24 * 60 * 60)

    # Fetch the price data from `get_price()`
    price_data = await get_price(token_address, last_week)

    if not price_data:
        return ("No price data available.")

    # Extract dates and prices for plotting
    dates = [datetime.strptime(str(data["date"]), "%Y%m%d") for data in price_data]
    prices = [data["price"] for data in price_data]

    # Create the plot
    plt.figure(figsize=(10, 5))
    plt.plot(dates, prices, marker='o', linestyle='-', color='b', label="Price")

    # Formatting the chart
    plt.title("Last week's daily price")
    plt.xticks(rotation=45)

    # Move y-axis (prices) to the right side
    plt.gca().yaxis.set_ticks_position('right')
    plt.gca().yaxis.set_label_position('right')

    # Remove the black outline around the chart
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['left'].set_visible(False)
    plt.gca().spines['bottom'].set_visible(False)

    # Display y-values in full (no scientific notation)
    ax = plt.gca()

    # Disable scientific notation on the y-axis
    ax.yaxis.set_major_formatter(ScalarFormatter())
    ax.yaxis.get_major_formatter().set_scientific(False)
    ax.yaxis.get_major_formatter().set_useOffset(False)

    # Use MaxNLocator to ensure y-axis ticks are well distributed
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, prune='both'))

    # Hide the x-axis
    plt.gca().get_xaxis().set_visible(False)

    # Display the grid
    plt.grid(True)

    # Save the plot to a BytesIO object instead of a file
    image_stream = BytesIO()
    plt.savefig(image_stream, format='png')
    image_stream.seek(0)  # Move the cursor to the start of the BytesIO object

    # Close the plot
    plt.close()

    return image_stream

