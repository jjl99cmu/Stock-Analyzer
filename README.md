# Stock-Analyzer
Evaluates given stock by displaying the correlation coefficient between stocks, avg price change, avg volume, price fluctuation, open close gap average.


------

How to create the CSV file:

First go to Yahoo Finance -> https://finance.yahoo.com/
Search fo rthe stock you want to analyze in the search bar.

Click on "Historical Data"

Set the time period to "Max".
Then press apply.
Click download.

Repeat these steps until you are satisfied with the number of stocks you want to analyze.

Then copy and past the data (merge) into one csv file.

Place it into your "stockdata" folder and place this folder into your 15-112 folder which should already have cmu_graphics installed.

Also, you will need to download an image (from https://unsplash.com/s/photos/candlestick-chart).
Then you need to title it candlestick4.jpg and place it into a folder called images and place that into your 15-112 folder as well.

You're all set!

------

No external modules are necessary. You can just run the code.

------

These shortcut commands are listed on the user interface:

Key shortcuts:
    - = and - to zoom in and out on both axis
    - [ and ] to zoom in and out on time axis

    Buttons:
    - +, auto, -: zoom price axis
    - sel: zoom to selection
    - +5, +1, -1, -5: change moving average width

    Magnify:
    - Click the magnify icon to select function
    - Click on the graph to zoom
    - Deselect magnify icon to de-select function
    
    Select:
    - Make sure a selection exists
    before clicking evaluate

    - When selecting new companies,
    click evaluate to update the chart

    - To create a selection,
    drag on the bottom part of the graph
