import cmu_graphics as c
import math
import os
import csv
import functools
from PIL import Image
from datetime import datetime, timedelta
from pprint import pprint

# --- Citations ---

# Credit to 15-112 for teaching me basic PIL methods
# Image downloaded from: https://unsplash.com/s/photos/candlestick-chart
# Also used Pixlr Editor to blur the image
image = Image.open("images/candlestick4.jpg")
image = c.CMUImage(image)

# strptime function: https://www.programiz.com/python-programming/datetime/strptime
# yield generator function: https://www.simplilearn.com/tutorials/python-tutorial/yield-in-python#:~:text=let's%20get%20started.-,What%20Is%20Yield%20In%20Python%3F,of%20simply%20returning%20a%20value.
# zip function: https://realpython.com/python-zip-function/#:~:text=Python's%20zip()%20function%20creates,programming%20problems%2C%20like%20creating%20dictionaries.
# exceptions (raise ValueError): https://docs.python.org/3/tutorial/errors.html 
# @property: https://www.freecodecamp.org/news/python-property-decorator/#:~:text=The%20%40property%20is%20a%20built,define%20properties%20in%20a%20class.
# @lru_cache: https://realpython.com/lru-cache-python/#:~:text=Python's%20%40lru_cache%20decorator%20offers%20a,entries%20will%20be%20ever%20evicted.
# lambda function: https://www.cs.cmu.edu/~112/notes/notes-functions-redux.html#lambdaFns
# timedelta object: https://docs.python.org/3/library/datetime.html#:~:text=A%20timedelta%20object%20represents%20a,between%20two%20dates%20or%20times.&text=All%20arguments%20are%20optional%20and,and%20microseconds%20are%20stored%20internally.
# extension function: https://stackoverflow.com/questions/3964681/find-all-files-in-a-directory-with-extension-txt-in-python and https://stackoverflow.com/questions/9234560/find-all-csv-files-in-a-directory-using-python
# datetime objects: https://www.w3schools.com/python/python_datetime.asp
# enumerate: https://realpython.com/python-enumerate/



# --- Initialize variables ---
app = c.app
rgb = c.rgb
tick = 0
debug = False
title = False if debug else True
companySelection = set()
accurateRenderMode = False
totalData = {}

# 1080p resolution
screenWidth = 1920
screenHeight = 1080

# Configurations
indent = 20
stockGraphBL = (420, screenHeight - 300)
stockGraphTR = (screenWidth - 200, 100)
stockSelectionDragZoneHeight = 35
fontSize = 36

# Colors
colorBG = rgb(38, 55, 85)
colorFG = rgb(255, 255, 252)
colorEvalBG = rgb(51, 64, 73)
colorButtonStart = rgb(24, 47, 64)
colorButtonBIG = rgb(40, 43, 51)
colorButtonCompany = rgb(53, 58, 69).lighter()
colorButtonCompanySelected = rgb(53, 58, 69).darker().darker()
colorButtonSmall = rgb(169, 151, 111)
colorButtonZoom = rgb(191, 46, 58)



# Class was created because there has to be a way to store
# the relational data between two companies without duplicates
class DoubleKeyDict:
    def __init__(self):
        self.dict = {}

    def get(self, k1, k2):
        if k1 > k2:
            k1, k2 = k2, k1
        # Return the value for the pair (k1, k2) in the dictionary
        return self.dict.get((k1, k2))

    def set(self, k1, k2, value):
        if k1 > k2:
            k1, k2 = k2, k1
        # Sets the value for the pair (k1, k2) in the dictionary
        self.dict[(k1, k2)] = value

    def __repr__(self):
        return repr(self.dict)

class Stock:
    def __init__(self, date, open, high, low, close, adjustedClose, volume):
        # Returns a datetime object that represents the date in year/month/day
        self.date = datetime.strptime(date, "%Y-%m-%d")
        self.open = float(open)
        self.high = float(high)
        self.low = float(low)
        self.close = float(close)
        self.adjustedClose = float(adjustedClose)
        self.volume = float(volume)

    # Create a read-only attribute to return POSIX timestamp
    @property
    def posixTime(self):
        # Returns the posix time of the stock
        return self.date.timestamp()

    def __repr__(self):
        return f"Stock(date={self.date}, open={self.open})"

class Company:
    # Stocks are sorted by date
    def __init__(self, name, ticker, stocks):
        self.name = name
        self.ticker = ticker
        self.stocks = stocks
        self.verify()

    # Verifies that the data is valid and sorted
    def verify(self):
        # Determine order stocks should be sorted
        self.stocks.sort(key=lambda s: s.date)
        # Checks
        for stock in self.stocks:
            if stock.high < stock.low:
                raise ValueError("High is less than low")
            if min(stock.open, stock.close) < stock.low:
                raise ValueError("Open or close is less than low")
            if max(stock.open, stock.close) > stock.high:
                raise ValueError("Open or close is greater than high")

    # Return company name and stock entries
    def __repr__(self):
        return f"Company({repr(self.name)}, stocks=[...{len(self.stocks)} entries])"

    # Calculates moving average of company's stock prices over given time frame
    def movingAverage(self, width):
        # Resolution is arbitrarily decreased in order to save memory
        if width < 2:
            return [s.close for s in self.stocks]
        return self.calculateMovingAverage(math.floor(width))

    # Memoization - speed up repeated calls with the same time frame
    @functools.lru_cache(maxsize=128)
    def calculateMovingAverage(self, width):
        # Returns the moving average of the stock prices
        prevTotalSum = self.stocks[0].close * width

        movingAverageList = []
        for i in range(0, len(self.stocks)):
            prevTotalSum += (self.stocks[i].close -
                             (self.stocks[i - width].close
                              if i >= width else self.stocks[0].close))
            movingAverageList.append(prevTotalSum / width)

        return movingAverageList

# Maps dates to integers and integers to dates
# Used to remove weekends from the graph
class DateMapper:
    def __init__(self, originDate):
        # Skip all weekends
        self.originDate = originDate
        self.datemap = {originDate: 0}
        self.reverseMap = {0: originDate}
        self.oldestDate = originDate
        self.newestDate = originDate

    def getDateIndex(self, targetDate):
        # If a weekend is provided, then return the closest future non-weekend
        # Saturday -> Monday
        if targetDate > self.newestDate:
            # Expand newest date
            prev = self.datemap[self.newestDate]
            while self.newestDate < targetDate:
                self.newestDate += timedelta(1)
                # 5 is saturday, 6 is sunday
                while self.newestDate.weekday() >= 5:
                    self.newestDate += timedelta(1)

                prev += 1
                self.datemap[self.newestDate] = prev
                self.reverseMap[prev] = self.newestDate

            return prev

        if targetDate < self.oldestDate:
            # Expand oldest date
            prev = self.datemap[self.oldestDate]
            while self.oldestDate > targetDate:
                self.oldestDate -= timedelta(1)
                while self.oldestDate.weekday() >= 5:
                    self.oldestDate -= timedelta(1)

                prev -= 1
                self.datemap[self.oldestDate] = prev
                self.reverseMap[prev] = self.oldestDate

            return prev

        while targetDate not in self.datemap:
            targetDate += timedelta(1)

        return self.datemap[targetDate]

    def getDateFromIndex(self, targetDate):
        if targetDate > self.datemap[self.newestDate]:
            # Expand newest date
            prev = self.datemap[self.newestDate]
            while self.datemap[self.newestDate] < targetDate:
                self.newestDate += timedelta(1)
                while self.newestDate.weekday() >= 5:
                    self.newestDate += timedelta(1)

                prev += 1
                self.datemap[self.newestDate] = prev
                self.reverseMap[prev] = self.newestDate

            return self.newestDate

        if targetDate < self.datemap[self.oldestDate]:
            # Expand oldest date
            prev = self.datemap[self.oldestDate]
            while self.datemap[self.oldestDate] > targetDate:
                self.oldestDate -= timedelta(1)
                while self.oldestDate.weekday() >= 5:
                    self.oldestDate -= timedelta(1)

                prev -= 1
                self.datemap[self.oldestDate] = prev
                self.reverseMap[prev] = self.oldestDate

            return self.oldestDate

        return self.reverseMap[targetDate]

# Button class that can draw a rectangle and a label at the same time
class Button:
    def __init__(self, text, x, y, w, h, rect={}, label={}, meta=None):
        self.text = text
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.rect = rect
        self.label = label
        self.meta = meta

    def draw(self):
        c.drawRect(self.x, self.y, self.w, self.h,
                   **{"border": None, **self.rect})
        # Always use white, bold, italic text
        c.drawLabel(self.text, self.x + self.w / 2, self.y + self.h / 2, 
                    **{"size": fontSize, **self.label}, italic=True,
                    bold=True, fill="white")

    # Returns whether the button contains the point (x, y)
    def contains(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h

class MagnifyingGlass:
    def __init__(self, x, y, text=""):
        self.x = x
        self.y = y
        self.text = text
        self.side = 70
        self.bg = rgb(0, 0, 0)
        self.selected = False

    def draw(self):
        self.bg = rgb(130, 130, 130) if self.selected else rgb(200, 200, 200)
        c.drawRect(self.x, self.y, self.side, self.side, fill=self.bg)
        c.drawCircle(self.x + self.side / 2 - 2, self.y + self.side / 2 - 2, 
                     self.side / 3, fill="black")
        # Draw handle
        c.drawRect(self.x + self.side / 2 + 10, self.y + self.side / 2 + 10, 
                   self.side / 2, self.side / 7, align="center", fill="black", 
                   rotateAngle=45)
        c.drawCircle(self.x + self.side / 2 - 2, self.y + self.side / 2 - 2, 
                     self.side / 5, fill=self.bg)

        # Draw text at bottom right
        c.drawLabel(self.text, self.x + self.side, self.y + self.side, size=20, 
                    fill="black", align="right-bottom")

    # Returns whether (x, y) is inside the magnifying glass icon
    def isInside(self, x, y):
        return (x > self.x and x < self.x + self.side 
                and y > self.y and y < self.y + self.side)

class StockGraph:
    def __init__(self, data, x, y, w, h, backgroundBorder=None,
                 background=None, border=None):
        self.data = data
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.backgroundBorder = backgroundBorder
        self.background = background
        self.border = border

        self.dragging = False
        self.prevAccuarteRender = False
        self.selecting = False

        self.mousePrev = (0, 0)
        self.userFocus = (0, 0)
        self.zoomX = 10.0
        self.zoomY = 200.0

        self.selectLeft = None
        self.selectRight = None

        # 10 is indent / spacing
        self.magnifyingGlassZoomIn = MagnifyingGlass(self.x + self.w - 80,
                                                     self.y + 10,
                                                     text="+")
        
        self.magnifyingGlassZoomOut = MagnifyingGlass(self.x + self.w - 80,
                                                      self.y + 10 + 80,
                                                      text="-")

        self.movingAverageWidth = 1

        self.rightMostDate = datetime(1984, 1, 1)
        self.leftMostDate = datetime(2077, 1, 1)
        self.dm = DateMapper(datetime(2010, 1, 1))

        self.highestPrice = self.lowestPrice = 0

        # When selection is updated, it is set to true
        self.evaluationStatus = True
        self.evaluationData = DoubleKeyDict()
        
        # company name:
        # [average price change, average volume, price fluctuation, gap average]
        self.evaluationStats = {}

    # Transforms virtual x, y coordinate to screen x, y coordinate
    def transform(self, lx, ly):
        screenX = (lx - self.userFocus[0]) * self.zoomX + self.w / 2
        screenY = (ly - self.userFocus[1]) * self.zoomY + self.h / 2
        return screenX + self.x, screenY + self.y

    # Inverse function of transform
    def reverseTransform(self, sx, sy):
        lx = (sx - self.x - self.w / 2) / self.zoomX + self.userFocus[0]
        ly = (sy - self.y - self.h / 2) / self.zoomY + self.userFocus[1]
        return lx, ly

    # Draws the stock graph to the screen
    def draw(self):
        if self.background:
            c.drawRect(self.x, self.y, self.w, self.h, fill=self.background, 
                       border=None)

            # Warn the user if there are no companies selected
            if not companySelection:
                c.drawLabel("No companies selected", self.x + self.w / 2, 
                            self.y + self.h / 2, size=fontSize, fill="black")

        scaledOffsetX, scaledOffsetY = self.transform(0, 0)

        step = max(1, math.floor(4 / self.zoomX)) if not accurateRenderMode else 1

        #left, right, top, bottom
        lrtb = (self.x, self.x + self.w, self.y, self.y + self.h)

        leftDate = self.dm.getDateFromIndex(modularMult(0,
                   self.reverseTransform(self.x - 30, 0)[0], 1))
        rightDate = self.dm.getDateFromIndex(modularMult(0,
                    self.reverseTransform(self.x + self.w + 30, 0)[0], 1))

        needsDateUpdate = True

        for key, company in self.data.items():
            if key not in companySelection:
                continue

            if needsDateUpdate:
                self.leftMostDate = company.stocks[0].date
                self.rightMostDate = company.stocks[-1].date
                needsDateUpdate = False

            self.leftMostDate = min(self.leftMostDate, company.stocks[0].date)
            self.rightMostDate = max(self.rightMostDate, company.stocks[-1].date)

            # Moving average absolute data
            ma = company.movingAverage(self.movingAverageWidth)

            # Moving average data that will be drawn
            maData = []
            prevPointDrawn = False
            prevSX = None
            for stockIdx, stock in (enumerate(company.stocks) if step <= 1
                                    else enumerateIterList(company.stocks, step)):
                # Fail fast - don't crash
                if stock.date < leftDate or stock.date > rightDate:
                    prevPointDrawn = False
                    continue

                visible, maVisible, sx, diff, barHeight = calculateStockGraphics(
                    stock, scaledOffsetX, scaledOffsetY, self.zoomX, 
                    self.zoomY, self.dm, self.zoomX * step, lrtb, 
                    movingAveragePoint=ma[stockIdx])

                # This is the first iteration,
                # set previous stock x to current stock x
                if prevSX is None:
                    prevSX = sx

                # If the moving average is visible, draw it
                if maVisible:
                    # If the previous point was not drawn,
                    # draw it, as it is the start of the line
                    if not prevPointDrawn and stockIdx != 0:
                        maData.append((prevSX, ma[stockIdx - 1], False))

                    maData.append((sx, ma[stockIdx], True))
                    prevPointDrawn = True
                else:
                    if prevPointDrawn:
                        maData.append((sx, ma[stockIdx], True))
                    prevPointDrawn = False

                # Set previous stock x to current stock x
                prevSX = sx

                # If the stock is not visible, skip it
                if not visible:
                    continue

                # Main stock bar
                c.drawRect(sx - self.zoomX / 2, 
                           scaledOffsetY - stock.close * self.zoomY if diff > 0 
                           else scaledOffsetY - stock.open * self.zoomY, 
                           self.zoomX, barHeight * self.zoomY, 
                           fill="green" if diff > 0 else "red")

                if accurateRenderMode or self.zoomX > 5:
                    # Draw high and low
                    c.drawLine(sx, scaledOffsetY - stock.high * self.zoomY, sx, 
                               scaledOffsetY - stock.low * self.zoomY, 
                               fill="green" if diff > 0 else "red")

            # Draw moving average
            drawLine([(x, scaledOffsetY - v * self.zoomY, b) for x, v, b in maData])

        # Draw selection area
        if self.selectLeft and self.selectRight:
            l = max(self.x, self.transform(self.selectLeft, 0)[0])
            r = min(self.x + self.w, self.transform(self.selectRight, 0)[0])
            if l < r:
                c.drawRect(l, self.y, r - l, self.h, fill="yellow", opacity=20, 
                           border=None)

        # Horizontal ticks (time)
        xInterval = 1
        for t in rangeStep(
            # 30 is the width of the text label for date
            modularMult(0, self.reverseTransform(self.x - 30, 0)[0], xInterval)
            + xInterval,
            modularMult(0, self.reverseTransform(self.x + self.w, 0)[0], xInterval)
            + xInterval,
            xInterval):

            d: datetime = self.dm.getDateFromIndex(t)
            rx = self.transform(t, 0)[0]
            if self.zoomX > 6:
                c.drawLine(rx, self.y + self.h, rx, self.y + self.h - 10)
                # Add label for date

            # Draw date label every 100 pixels
            if t % math.ceil(100 / self.zoomX) == 0:
                # Draw year if zoome out
                c.drawLabel(d.strftime("%m-%d")
                            if self.zoomX > 0.4 else d.strftime("%Y"), 
                            rx, self.y + self.h - 10, size=10,
                            align="left-bottom", rotateAngle=-45)

        # Vertical ticks (price)
        # Calculate the appropriate y interval (in power of 10) for stock prices
        # This allows the label to not be cluttered
        yInterval = 1 / 10 / 10 ** math.floor(math.log(2 * self.zoomY / self.h, 10))
        for t in rangeStep(-modularMult(0, -self.reverseTransform(0, self.y)[1], yInterval), 
                           -modularMult(0, -self.reverseTransform(0, self.y + self.h)[1], yInterval), 
                           yInterval):
            ry = self.transform(0, t)[1]
            c.drawLine(self.x, ry, self.x + 10, ry)
            # Add label for price
            c.drawLabel(f"{-round(t, 2):.2f}", self.x + 10, ry, size=10, align="left")

        # Draw the magnifying glass
        self.magnifyingGlassZoomIn.draw()
        self.magnifyingGlassZoomOut.draw()

        borderThickness = 400

        if self.backgroundBorder:
            # Draw rectangles around the border so there is no text spill

            widthHeight = ((borderThickness * 2 + self.w, borderThickness),
                           (borderThickness, borderThickness * 2 + self.h))

            xy = (self.x - borderThickness, self.y - borderThickness)
            c.drawRect(*xy, *widthHeight[0], fill=self.backgroundBorder)
            c.drawRect(*xy, *widthHeight[1], fill=self.backgroundBorder)
            c.drawRect(xy[0], xy[1] + self.h + borderThickness, 
                       *widthHeight[0], fill=self.backgroundBorder)
            c.drawRect(xy[0] + self.w + borderThickness, xy[1],
                       *widthHeight[1], fill=self.backgroundBorder)

        if self.border:
            c.drawRect(self.x, self.y, self.w, self.h, fill=None, 
                       border=self.border, borderWidth=2)

        # Additional data / statistics
        # Draw year label
        ma = math.floor(self.movingAverageWidth)
        c.drawLabel(leftDate.strftime("%Y") + " - " 
                    + f"Moving average: {ma} day"
                    + ("" if ma == 1 else "s"), self.x + 5,
                    self.y + self.h + 5, align="left-top",
                    size=15, fill=colorFG)

    # assigns self.highestPrice and self.lowestPrice
    def calculateHighestAndLowest(self):
        if not companySelection:
            return

        self.highestPrice = float("-inf")
        self.lowestPrice = float("inf")

        leftDate = self.dm.getDateFromIndex(modularMult(0,
                   self.reverseTransform(self.x - 30, 0)[0], 1))
        rightDate = self.dm.getDateFromIndex(modularMult(0,
                    self.reverseTransform(self.x + self.w + 30, 0)[0], 1))
        
        for key, company in self.data.items():
            if key not in companySelection:
                continue
            for stock in company.stocks:
                # Fail fast - don't crash
                if stock.date < leftDate or stock.date > rightDate:
                    continue

                if stock.high > self.highestPrice:
                    self.highestPrice = stock.high

                if stock.low < self.lowestPrice:
                    self.lowestPrice = stock.low

    def autoZoomY(self):
        # Make sure to call calculateHighestAndLowest before calling this
        self.userFocus = (self.userFocus[0],
                          -(self.highestPrice + self.lowestPrice) / 2)
        self.zoomY = self.h / (max(0.05, self.highestPrice - self.lowestPrice))

    # Zooms to selection
    def zoomToSelection(self):
        if (not self.selectLeft or not self.selectRight 
            or self.selectRight <= self.selectLeft):
            return

        self.userFocus = ((self.selectLeft + self.selectRight) / 2, 
                          self.userFocus[1])
        self.zoomX = self.w / (self.selectRight - self.selectLeft)

        self.autoZoomY()

    # Sets status to False
    def evaluateSelection(self):
        self.evaluationData = DoubleKeyDict()
        self.evaluationStats.clear()

        if (not self.selectLeft or not self.selectRight 
            or self.selectRight <= self.selectLeft):
            return

        leftDate = self.dm.getDateFromIndex(math.floor(self.selectLeft))
        rightDate = self.dm.getDateFromIndex(math.ceil(self.selectRight))

        companyOpenCloseAvgData = {c: {s.date: (s.open + s.close) / 2
                                       for s in self.data[c].stocks
                                       if leftDate < s.date < rightDate}
                                       for c in companySelection}

        for c1 in companySelection:
            for c2 in companySelection:
                if c1 == c2:
                    self.evaluationData.set(c1, c2, 1)
                    continue

                # Entry already exists
                if self.evaluationData.get(c1, c2) is not None:
                    continue

                # Calculate correlation
                xs = []
                ys = []
                for date, openClose in companyOpenCloseAvgData[c1].items():
                    if date in companyOpenCloseAvgData[c2]:
                        xs.append(openClose)
                        ys.append(companyOpenCloseAvgData[c2][date])

                r = correlation(xs, ys)
                self.evaluationData.set(c1, c2, r)

        # Calculate stats
        for c in companySelection:
            # find first match
            first = None
            firstIdx = None
            data = None
            for firstIdx, first in enumerate(self.data[c].stocks):
                if first.date >= leftDate:
                    break

            # If first match is not suitable (more than 4 days old), None
            if not first or first.date - leftDate > timedelta(days=4):
                self.evaluationStats[c] = data
                continue

            # Find last match
            last = None
            lastIdx = None
            for idx, last in enumerate(self.data[c].stocks):
                if last.date > rightDate:
                    lastIdx = idx
                    break

            # If last match is not suitable (more than 4 days old), None
            if not last or rightDate - last.date > timedelta(days=4):
                self.evaluationStats[c] = data
                continue

            if firstIdx is None or lastIdx is None:
                self.evaluationStats[c] = data
                continue

            data = [0.0, 0.0, 0.0, 0.0]
            # Calculate statistics
            data[0] = ((self.data[c].stocks[lastIdx].open -
                        self.data[c].stocks[firstIdx].open) /
                        ((lastIdx - firstIdx) * 7 / 5))
            data[1] = average([s.volume for s in self.data[c].stocks[firstIdx:lastIdx]])
            gaps = [s.close - s.open for s in self.data[c].stocks[firstIdx:lastIdx]]
            data[2] = stdDev(gaps)
            data[3] = average([abs(g) for g in gaps])

            self.evaluationStats[c] = data

        self.evaluationStatus = False

    # Handle mouse presses
    def onMousePress(self, x, y):
        # Check if mouse is in graph
        if self.magnifyingGlassZoomIn.isInside(x, y):
            self.magnifyingGlassZoomIn.selected = not self.magnifyingGlassZoomIn.selected
            self.magnifyingGlassZoomOut.selected = False
            return
        if self.magnifyingGlassZoomOut.isInside(x, y):
            self.magnifyingGlassZoomOut.selected = not self.magnifyingGlassZoomOut.selected
            self.magnifyingGlassZoomIn.selected = False
            return

        if self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h:
            if (self.magnifyingGlassZoomIn.selected 
                or self.magnifyingGlassZoomOut.selected):
                ux, uy = self.reverseTransform(x, y)

                self.userFocus = ux, uy

                # Increase zoom
                self.zoomX *= 1.5 if self.magnifyingGlassZoomIn.selected else 0.5

                # Quality of life improvements
                self.calculateHighestAndLowest()
                self.autoZoomY()

                return

            # Acess accurateRenderMode
            global accurateRenderMode
            self.prevAccuarteRender = accurateRenderMode
            if y <= self.y + self.h - stockSelectionDragZoneHeight:
                # Dragging area
                accurateRenderMode = False
                self.dragging = True
            else:
                self.selecting = True
                self.evaluationStatus = True
                self.selectLeft = self.reverseTransform(x, y)[0]
                self.selectRight = self.reverseTransform(x, y)[0]
            self.mousePrev = (x, y)

    # Handle mouse drag
    def onMouseDrag(self, x, y):
        # If dragging, move graph
        # If selecting, update selection
        if self.dragging:
            self.userFocus = (self.userFocus[0] + (self.mousePrev[0] - x) / self.zoomX, 
                              self.userFocus[1] + (self.mousePrev[1] - y) / self.zoomY)
            self.mousePrev = (x, y)

        if self.selecting:
            # Check if dragging left or right
            if x > self.mousePrev[0]:
                # Going right, update selection right
                self.selectRight = self.reverseTransform(x, y)[0]
            else:
                # Going left, update selection left
                self.selectLeft = self.reverseTransform(x, y)[0]

    # Handle mouse release
    def onMouseRelease(self, x, y):
        # If dragging, stop dragging
        # If selecting, evaluate selection
        if self.selecting or self.dragging:
            global accurateRenderMode
            accurateRenderMode = self.prevAccuarteRender
        if self.selecting:
            self.evaluateSelection()
        self.dragging = False
        self.selecting = False

    # Handle keyholds - shortcuts (displayed on screen as well)
    def onKeyHold(self, keys):
        if "=" in keys:
            self.zoomX *= 1.1
            self.zoomY *= 1.1
        elif "-" in keys:
            self.zoomX /= 1.1
            self.zoomY /= 1.1
        if "[" in keys:
            self.zoomX /= 1.1
        elif "]" in keys:
            self.zoomX *= 1.1



# Splits the input list L into sublists of size n
# Returns them one at a time
def splitList(L, n):
    # Split the list into sublists of equal size
    # If n not given
    if n == -1:
        n = len(L)

    # Returns the sublists one at a time
    for i in range(0, len(L), n):
        yield L[i : i + n]

# Returns a new lowercase string 
# All spaces are replaced with underscores
def formatName(name):
    name = name.lower()
    return name.replace(" ", "_")

# Returns the number with the sign preserved
def strWithSign(num):
    # e.g.
    # strWithSign(1) -> "+1"
    if num > 0:
        return f"+{num}"
    return str(num)

# Returns a list of tuples
# tuple contains two adjacent elements from L
def zipPair(L):
    # zipPair([1, 2, 3, 4]) -> [(1, 2), (2, 3), (3, 4)]
    return list(zip(L, L[1:]))

# Returns the average of a list
def average(L):
    return sum(L) / len(L)

# Returns the standard deviation of a list
def stdDev(L):
    # Calculate the average of the list
    mean = sum(L) / len(L)

    # Calculate sum of squared differences between each element and the average
    variance = sum((i - mean) ** 2 for i in L) / len(L)

    # Return square root of the variance (aka standard deviation)
    return math.sqrt(variance)

# Returns the correlation between two lists
def correlation(L1, L2):
    #check lists have the same number of elements
    if len(L1) != len(L2):
        raise ValueError("Lists are not the same length")

    # no linear relationship exists exists
    # if correlation coefficient is 0
    if len(L1) == 0:
        return 0

    mean1 = sum(L1) / len(L1)
    mean2 = sum(L2) / len(L2)

    numerator = sum((x - mean1) * (y - mean2) for x, y in zip(L1, L2))
    denominator = (math.sqrt(sum((x - mean1) ** 2 for x in L1)
                             * sum((y - mean2) ** 2 for y in L2)))

    if denominator == 0:
        return 0

    #return the correlation coefficient
    return numerator / denominator

# Returns a list of file names in a directory with a certain extension
def fileNamesInDir(dirName, extension=".csv"):
    # Used to get all the csv files in the data directory and load them
    return [fileName for fileName in os.listdir(dirName)
            if fileName.endswith(extension)]

def readCSVrows(filename, categoryLength=-1):
    # Create a csv reader
    datareader = csv.reader(filename, delimiter=",")

    # Skip the first row
    companies = [company for company in next(datareader) if company != ""]

    # Skip the second row
    categories = next(datareader)

    # Normalize the category names for better reading and storing as JSON
    categories = [formatName(s) for s in categories[:categoryLength]]

    # Create a dictionary of companies
    stockData = {copmanyName: Company(copmanyName, copmanyName, []) 
                 for copmanyName in companies}

    # Read the rows
    for row in datareader:
        # Split the row into parts using the category length
        parts = splitList(row, categoryLength)
        for company, part in zip(companies, parts):
            # If the first part is empty, assume that the rest of the parts are empty
            if part[0] == "":
                continue

            # Add the stock to the company
            stockData[company].stocks.append(Stock(*part[: categoryLength - 1]))

    # Verify that the data is valid
    for company in stockData.values():
        company.verify()

    return stockData

for file in fileNamesInDir("stockdata"):
    data = readCSVrows(open(f"stockdata/{file}"), 8)
    print("Reading", file, "with", len(data), "companies")
    totalData.update(data)

# Warn the user if there is no data
if len(totalData) == 0:
    print()
    print("=" * 80)

    # os.getcwd() returns the string for the current dictionary
    print(f"""No data found. Please make sure that stockdata at the directory
        {os.getcwd()} is not empty and has valid .csv files""")
    print("=" * 80)
    print()

width = stockGraphBL[0] - indent * 2
buttonHeight = ((screenHeight - stockGraphBL[1]) - indent * 4) // 4

buttonClearAllSelection = Button("Clear All Selections", indent, 
                                 stockGraphBL[1] + indent * 1, width, 
                                 buttonHeight, rect={"fill": colorButtonBIG})

buttonRenderMode = Button("PLACEHOLDER", indent, 
                          stockGraphBL[1] + indent * 2 + buttonHeight, 
                          width, buttonHeight, rect={"fill": colorButtonBIG})

buttonEvaluate = Button("Evaluate", indent, 
                        stockGraphBL[1] + indent * 3 + buttonHeight * 2, 
                        width, buttonHeight * 2, rect={"fill": colorButtonBIG})

companyHeight = indent / 2 + fontSize

buttonsCompanies = [Button(company.name, indent, 
                           stockGraphTR[1] + idx * (companyHeight + indent / 2), 
                           width, companyHeight, 
                           rect={"fill": colorButtonCompany}, meta=key) 
                           for idx, (key, company) in enumerate(totalData.items())]

# Bottom up
diffs = (-5, -1, 1, 5)

# *moving average button
mabHeight = 2 * indent + fontSize
mabWidth = (screenWidth - stockGraphTR[0]) - indent * 2
buttonsMovingAverage = [Button(strWithSign(diff), stockGraphTR[0] + indent, 
                               stockGraphBL[1] - idx * (mabHeight + indent)
                               - mabHeight, mabWidth, mabHeight, meta=diff, 
                               rect={"fill": colorButtonSmall}) 
                               for idx, diff in enumerate(diffs)]

# Equal partition for intervals
timespans = [("all time", float("inf")), 
             # Have to exclude weekends, hence the 5/7 
             ("3 years", math.floor(3 * 365 * 5 / 7)), 
             ("1 year", math.floor(365 * 5 / 7)), 
             ("3 months", math.floor(365 / 4 * 5 / 7)), 
             ("1 month", math.floor(365 / 12 * 5 / 7)), 
             ("1 week", math.floor(5))]

stockWidth = stockGraphTR[0] - stockGraphBL[0]
timespanWidth = (stockWidth - indent * (len(timespans) - 1)) / len(timespans)
timespanHeight = stockGraphTR[1] - 2 * indent

buttonsTimespan = [Button(duration, 
                          stockGraphBL[0] + idx * (timespanWidth + indent), 
                          indent, timespanWidth, timespanHeight, meta=days) 
                          for idx, (duration, days) in enumerate(timespans)]

yZoomHeight = timespanHeight
yZoomLabels = ["+", "auto", "-", "sel"]

buttonsYZoom = [Button(label, stockGraphTR[0] + indent, 
                       indent + idx * (yZoomHeight + indent), mabWidth, 
                       yZoomHeight, meta=label, rect={"fill": colorButtonZoom}) 
                       for idx, label in enumerate(yZoomLabels)]

buttonsYZoom[-1].rect["fill"] = colorButtonSmall

buttonStart = Button("Start", screenWidth / 2 - 250, screenHeight / 2,
                     450, 200, rect={"fill": colorButtonStart},
                     label={"size": 100})

def calculateStockGraphics(stock, x, y, xScale, yScale, datemap, 
                           barWidth=None, lrtb=(0, 0, 0, screenHeight), 
                           movingAveragePoint=None):
    # x, y: origin (x is date)
    # xScale: how many pixels per day
    # yScale: how many pixels per unit currency

    # Get height of stock bar
    diff = stock.close - stock.open
    h = max(0.00001, abs(diff))

    dateIdx = datemap.getDateIndex(stock.date)
    sx = dateIdx * xScale + x

    barWidth = barWidth or xScale

    # Check if the stock bar is visible
    visible = not isOutside(sx, y, -barWidth / 2 + lrtb[0], 
                            barWidth / 2 + lrtb[1], 
                            stock.low * yScale + lrtb[2], 
                            stock.high * yScale + lrtb[3])

    # Check if the moving average is visible
    maVisible = (movingAveragePoint is not None
                 and not isOutside(sx, y, -barWidth + lrtb[0], 
                                   barWidth + lrtb[1], 
                                   movingAveragePoint * yScale + lrtb[2], 
                                   movingAveragePoint * yScale + lrtb[3]))

    return visible, maVisible, sx, diff, h

# Checks if a point is outside a rectangle
def isOutside(x, y, left, right, top, bottom):
    # Note that top is higher on the screen
    # top < bottom
    return x < left or x > right or y < top or y > bottom

# Iterates through a range with a step (support floats)
def rangeStep(start, end, step: float = 1):
    while start < end:
        yield start
        start += step

# Iterates through a list with a step
def enumerateIterList(L, step):
    for i in range(0, len(L), step):
        yield i, L[i]

# Modular Multiplication
def modularMult(n, lim, d):
    # Adds the remainder of n divided by d to the highest multiple of d
    # e.g.
    # modularMult(11, 8, 3) -> (11 % 3) + (3 * (8 // 3)) -> 2 + 3 * 2 = 8
    return (n % d) + (d * (lim // d))

# Draws a line with multiple points
def drawLine(points, fill="black", lineWidth=2):
    for p1, p2 in zipPair(points):
        if not p2[2]:
            continue
        c.drawLine(p1[0], p1[1], p2[0], p2[1], fill=fill, lineWidth=lineWidth)

stockGraph = StockGraph(totalData, stockGraphBL[0], stockGraphTR[1], 
                        stockGraphTR[0] - stockGraphBL[0], 
                        stockGraphBL[1] - stockGraphTR[1], 
                        backgroundBorder=colorBG, 
                        background=colorFG, border="black")

# Handles mouse drag
def onMouseDrag(app, x, y):
    if title:
        return
    stockGraph.onMouseDrag(x, y)

# Handles mouse press
def onMousePress(app, x, y):
    global title
    if title:
        if buttonStart.contains(x, y):
            title = False
        return

    stockGraph.onMousePress(x, y)

    # check if user clicked Render Mode button
    # change to fast or accurate
    if buttonRenderMode.contains(x, y):
        global accurateRenderMode
        accurateRenderMode = not accurateRenderMode
        return

    # check if user clikced Clear All Selection button
    if buttonClearAllSelection.contains(x, y):
        companySelection.clear()
        return

    # check if user clicked on Evaluate
    # Evaluate is also automatic
    if buttonEvaluate.contains(x, y):
        stockGraph.evaluateSelection()
        return

    # check if user added / removed companies
    # select / de-select companies to be displayed
    for cb in buttonsCompanies:
        if cb.contains(x, y):
            if cb.meta in companySelection:
                companySelection.remove(cb.meta)
            else:
                companySelection.add(cb.meta)
            return

    # check if user changed the moving average
    for mab in buttonsMovingAverage:
        if mab.contains(x, y):
            stockGraph.movingAverageWidth = (max(1, stockGraph.movingAverageWidth
                                                 + mab.meta))
            return

    # change horizontal zoom of stockGraph based on button
    if companySelection:
        for tsb in buttonsTimespan:
            if tsb.contains(x, y):
                d: float = tsb.meta
                if d == float("inf"):
                    stockGraph.zoomX = ((stockGraph.w /
                                         (((stockGraph.rightMostDate
                                            - stockGraph.leftMostDate).days)
                                            * 5 / 7)) * 0.8)
                    stockGraph.userFocus = (
                        (stockGraph.dm.getDateIndex(stockGraph.leftMostDate) 
                         + stockGraph.dm.getDateIndex(stockGraph.rightMostDate)) 
                         / 2, 0)
                    stockGraph.calculateHighestAndLowest()
                    stockGraph.autoZoomY()
                else:
                    stockGraph.zoomX = stockGraph.w / d

    # adjusts vertical zoom based on button press
    for yzb in buttonsYZoom:
        if yzb.contains(x, y):
            if yzb.meta == "auto":
                stockGraph.calculateHighestAndLowest()
                stockGraph.autoZoomY()
            elif yzb.meta == "+":
                stockGraph.zoomY *= 1.4
            elif yzb.meta == "-":
                stockGraph.zoomY /= 1.4
            elif yzb.meta == "sel":
                stockGraph.calculateHighestAndLowest()
                stockGraph.zoomToSelection()

# Handles mouse release
def onMouseRelease(app, x, y):
    if title:
        return
    stockGraph.onMouseRelease(x, y)

# Handle keyholds
def onKeyHold(app, keys):
    if title:
        return
    stockGraph.onKeyHold(keys)

# Handle key presses
def onKeyPress(app, key):
    # was used for debugging
    # helped to remove excess graphs of stocks from showing
    global debug
    if key == "d":
        debug = not debug
        stockGraph.backgroundBorder = colorBG if not debug else None

    if title:
        return

def drawTitle():
    # Draw background and change image size to fit high res
    c.drawImage(image,0,0,width=1920,height=1080)

    #Draw stock analyzer title
    c.drawLabel("Stock Analyzer", screenWidth / 2, screenHeight / 4, 
                fill=colorFG, italic=True, bold=True, size=200)

    buttonStart.draw()

def redrawAll(app):
    global tick

    if title:
        drawTitle()
        return

    stockGraph.draw()

    # Draw operating buttons
    buttonRenderMode.text = "Render mode: " + ("accurate" if accurateRenderMode
                                               else "fast")

    buttons = [buttonClearAllSelection, buttonRenderMode, buttonEvaluate]

    for button in buttons:
        button.draw()

    for button in buttonsCompanies:
        button.rect["fill"] = (colorButtonCompanySelected 
                               if button.meta in companySelection 
                               else colorButtonCompany)
        button.draw()

    for button in buttonsMovingAverage:
        button.draw()

    for button in buttonsTimespan:
        button.draw()

    for button in buttonsYZoom:
        button.draw()

    # Draw time at top left
    c.drawLabel(f"{datetime.now().strftime('%Y-%m-%d | %H:%M:%S')}", 
                stockGraphBL[0] // 2, stockGraphTR[1] // 2, 
                size=fontSize, fill=colorFG)

    instructions = reversed(
        [line.lstrip() for line in """
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
    """.splitlines()])

    # Draw instructions from bottom up
    for idx, instruction in enumerate(instructions):
        c.drawLabel(instruction, indent,
                    stockGraphBL[1] - idx * fontSize / 2.5, 
                    size=fontSize / 2.5, fill=colorFG, 
                    align="left-bottom")

    # Draw grid of evaluation
    cellHeight = (((screenHeight - stockGraphBL[1]) - 2 * indent) / 
                  (len(companySelection) + 1))
    totalWidth = screenHeight - stockGraphBL[1]
    totalHeight = (len(companySelection) + 1) * cellHeight
    firstColumnWidth = totalWidth - len(companySelection) * cellHeight

    # Draw background
    c.drawRect(stockGraphBL[0], stockGraphBL[1] + indent, totalWidth, 
               totalHeight, fill=colorEvalBG)

    csl = list(companySelection)

    # Draw evaluation
    for i, c1 in enumerate(csl):
        for j, c2 in enumerate(csl):
            # Gray if same company
            # Green if correlation is positive
            # Red if correlation is negative
            fill = None
            if i == j:
                fill = "gray"
            else:
                correlationR = stockGraph.evaluationData.get(c1, c2)
                if correlationR is None:
                    fill = None
                else:
                    correlationR = max(0, min(2, 1 + correlationR))
                    fill = rgb(127.5 * (2 - correlationR), 
                               127.5 * correlationR, 0)

            if fill:
                c.drawRect(stockGraphBL[0] + firstColumnWidth + i * cellHeight, 
                           stockGraphBL[1] + indent + (j + 1) * cellHeight, 
                           cellHeight, cellHeight, fill=fill)

    # Draw row lines
    for i in range(len(companySelection) + 1 + 1):
        c.drawLine(stockGraphBL[0], stockGraphBL[1] + indent + i * cellHeight, 
                   stockGraphBL[0] + firstColumnWidth 
                   + len(companySelection) * cellHeight, 
                   stockGraphBL[1] + indent + i * cellHeight, 
                   fill=colorFG, lineWidth=1)
        # Draw company name
        if i > 0 and i <= len(companySelection):
            c.drawLabel(csl[i - 1], 
                        stockGraphBL[0] + firstColumnWidth - indent, 
                        stockGraphBL[1] + indent + (i + 0.5) * cellHeight, 
                        size=fontSize / 2, fill=colorFG, align="right")

    # Draw column lines
    c.drawLine(stockGraphBL[0], stockGraphBL[1] + indent, stockGraphBL[0], 
               screenHeight - indent, fill=colorFG, lineWidth=1)
    for i in range(len(companySelection) + 1):
        c.drawLine(stockGraphBL[0] + firstColumnWidth + i * cellHeight, 
                   stockGraphBL[1] + indent, 
                   stockGraphBL[0] + firstColumnWidth + i * cellHeight, 
                   screenHeight - indent, fill=colorFG, lineWidth=1)
        # Draw company name first letter
        if i > 0:
            c.drawLabel(csl[i - 1][0], 
                        stockGraphBL[0] + firstColumnWidth + (i - 0.5) * cellHeight, 
                        stockGraphBL[1] + indent + cellHeight / 2, 
                        size=fontSize, fill=colorFG, align="center")

    # Draw chart
    chartStartX = stockGraphBL[0] + totalWidth + indent
    chartTotalWidth = screenWidth - chartStartX - indent
    headers = ["Avg Price Change", "Avg Volume", "Price Fluctuation", 
               "Open Close Gap Average"]
    chartColumnWidth = (chartTotalWidth - firstColumnWidth) / 4

    # Draw background
    c.drawRect(chartStartX, stockGraphBL[1] + indent, chartTotalWidth, 
               totalHeight, fill=colorEvalBG)

    # Draw row lines
    for i in range(len(companySelection) + 1 + 1):
        c.drawLine(chartStartX, stockGraphBL[1] + indent + i * cellHeight, 
                   chartStartX + chartTotalWidth, 
                   stockGraphBL[1] + indent + i * cellHeight, 
                   fill=colorFG, lineWidth=1)
        # Draw company name
        if i > 0 and i <= len(companySelection):
            c.drawLabel(csl[i - 1], chartStartX + firstColumnWidth - indent, 
                        stockGraphBL[1] + indent + (i + 0.5) * cellHeight, 
                        size=fontSize / 2, fill=colorFG, align="right")

    # Draw column lines
    c.drawLine(chartStartX, stockGraphBL[1] + indent, chartStartX,
               screenHeight - indent, fill=colorFG, lineWidth=1)
    for i in range(len(headers) + 1):
        c.drawLine(chartStartX + firstColumnWidth + i * chartColumnWidth, 
                   stockGraphBL[1] + indent, 
                   chartStartX + firstColumnWidth + i * chartColumnWidth, 
                   screenHeight - indent, fill=colorFG, lineWidth=1)
        # Draw headers
        if i > 0:
            c.drawLabel(headers[i - 1], chartStartX +
                        firstColumnWidth + (i - 0.5) * chartColumnWidth, 
                        stockGraphBL[1] + indent + cellHeight / 2, 
                        size=fontSize / 2, fill=colorFG, align="center")

    # Draw stats
    for i, comp in enumerate(companySelection):
        r = stockGraph.evaluationStats.get(comp)
        for j in range(len(headers)):
            c.drawLabel(f"{r[j]:.2f}" if r is not None else "N/A", chartStartX 
                        + firstColumnWidth + j * chartColumnWidth + indent, 
                        stockGraphBL[1] + indent + (i + 1.5) * cellHeight, 
                        size=fontSize / 2, fill=colorFG, align="left")

def onStep(app):
    global tick
    tick += 1

app.background = colorBG

# don't crash
app.setMaxShapeCount(50000)

c.runApp(screenWidth, screenHeight)