from datetime import datetime

from cassandra.cluster import Cluster
from cassandra.query import named_tuple_factory

from pyspark import SparkContext, SparkConf
from pyspark.ml.regression import LinearRegression, LinearRegressionModel
from pyspark.ml.tuning import TrainValidationSplitModel, ParamGridBuilder

from pyspark.ml.feature import VectorAssembler
from pyspark.sql.functions import max, min, col, avg, count
from pyspark.sql.types import *
from pyspark.sql.functions import *
from pyspark.sql.functions import UserDefinedFunction

from utils import generalFunctions

import os
import time
import pickle
import json
import pyspark
import logging
FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(format=FORMAT,level=logging.INFO)
logger = logging.getLogger('sparkFunctions')



def getWeatherDataInterval(clean_daily, station_id, dateFrom, dateTo):
    datetime_object_to = datetime.strptime(dateTo, '%Y-%m-%d').date()
    datetime_object_from = datetime.strptime(dateFrom, '%Y-%m-%d').date()

    measurements = clean_daily.filter((clean_daily.measure_date >= datetime_object_from) &
                                      (clean_daily.measure_date <= datetime_object_to) & (
                                      clean_daily.station_id == station_id))

    return measurements


def getConcreteWeatherData(daily_measures, station_id, date, allStations):
    datetime_object = datetime.strptime(date, '%Y-%m-%d').date()

    if str(allStations) == str("True"):
        logger.info("All Stations")
        measurement = daily_measures.filter((daily_measures.measure_date == datetime_object))
    else:
        logger.info("One Station")
        measurement = daily_measures.filter(
            (daily_measures.measure_date == datetime_object) & (daily_measures.station_id == station_id))

    return measurement


def getConcreteEarhquakesDataWithQuadrants(earthquakes, date, maxY, minY, maxX, minX):
    datetime_object = datetime.strptime(date, '%Y-%m-%d').date()

    if maxY is not None and minY is not None and maxX is not None and minX is not None:
           
        earthquakesResult = earthquakes.filter((earthquakes.quadrantX <= maxX) & (earthquakes.quadrantX >= minX)
                                               & (earthquakes.quadrantY <= maxY) & (earthquakes.quadrantY >= minY) 
                                               & (earthquakes.fecha >= datetime_object))
     
    else:
        earthquakesResult = earthquakes.filter(earthquakes.fecha >= datetime_object)

    earthquakesReturn = earthquakesResult.sort(asc("fecha"))
    return earthquakesReturn.na.fill(0)


def getConcreteEarhquakesData(earthquakes, date, max_lat, min_lat, max_lon, min_lon):
    datetime_object = datetime.strptime(date, '%Y-%m-%d').date()

    if max_lon is not None and min_lon is not None and max_lat is not None and min_lat is not None:
        logger.info("Filtering by lat,lon and date")
        earthquakesResult = earthquakes.filter((earthquakes.fecha >= datetime_object) & (earthquakes.longitude <= max_lon) & (earthquakes.longitude >= min_lon)
                                               & (earthquakes.latitude <= max_lat) & (earthquakes.latitude >= min_lat))
    else:
        earthquakesResult = earthquakes.filter(earthquakes.fecha >= datetime_object)

    earthquakesReturn = earthquakesResult.sort(asc("fecha"))
    return earthquakesReturn.na.fill(0)


def getConcreteEarhquakesIntervalData(earthquakes, dateFrom, dateTo, max_lat, min_lat, max_lon, min_lon):
    dateFromtime_object = datetime.strptime(dateFrom, '%Y-%m-%d').date()
    dateTotime_object = datetime.strptime(dateTo, '%Y-%m-%d').date()

    if max_lon is not None and min_lon is not None and max_lat is not None and min_lat is not None:
        logger.info("Filtering by lat,lon and date")
        earthquakesByDate = earthquakes.filter((earthquakes.fecha >= dateFromtime_object) & (earthquakes.fecha <= dateTotime_object))
        earthquakesResult = earthquakesByDate.filter((earthquakes.longitude <= max_lon) & (earthquakes.longitude >= min_lon) & (earthquakes.latitude <= max_lat) & (earthquakes.latitude >= min_lat))
    else:
        earthquakesResult = earthquakes.filter((earthquakes.fecha >= dateFromtime_object) & (earthquakes.fecha <= dateTotime_object))

    earthquakesReturn = earthquakesResult.sort(asc("fecha"))
    return earthquakesReturn.na.fill(0)

def getConcreteEarhquakesIntervalDataWithQuadrants(earthquakes, dateFrom, dateTo, maxY, minY, maxX, minX):
    dateFromtime_object = datetime.strptime(dateFrom, '%Y-%m-%d').date()
    dateTotime_object = datetime.strptime(dateTo, '%Y-%m-%d').date()

    if maxY is not None and minY is not None and maxX is not None and minX is not None:
           
        earthquakesResult = earthquakes.filter((earthquakes.quadrantX <= maxX) & (earthquakes.quadrantX >= minX)
                                               & (earthquakes.quadrantY <= maxY) & (earthquakes.quadrantY >= minY) 
                                               & (earthquakes.fecha >= dateFromtime_object) & (earthquakes.fecha <= dateTotime_object))
     
    else:
        earthquakesResult = earthquakes.filter((earthquakes.fecha >= dateFromtime_object) & (earthquakes.fecha <= dateTotime_object))

    earthquakesReturn = earthquakesResult.sort(asc("fecha"))
    return earthquakesReturn.na.fill(0)


def getStationInfo(stations, station_id):
    stationData = stations.filter(stations.station_id == station_id)
    return stationData


def loadModelFromDatabase(columnName, station_id):
    cluster = Cluster(['192.168.246.236'])
    session = cluster.connect("dev")
    name = str(station_id + "__" + columnName)
    query = "SELECT model FROM linear_model WHERE name=%s"
    rows = session.execute(query, parameters=[(name)])
    # rows = session.execute('SELECT model FROM linear_model WHERE name=\"'+name+'\"')
    if (rows):
        for row in rows:
            loadedCustomModel = pickle.loads(row[0])
            loadedModel = loadedCustomModel.getModel()

            lrModel = TrainValidationSplitModel(loadedModel)
            return row[0]


def predictStats(fecha, station_id, station_daily):
    datetime_object = datetime.strptime(fecha, '%Y-%m-%d').date()

    newdf = station_daily.select(month(station_daily.measure_date).alias('dt_month'),
                                 dayofmonth(station_daily.measure_date).alias('dt_day'),
                                 station_daily.max_temp, station_daily.med_temp, station_daily.min_temp,
                                 station_daily.max_pressure, station_daily.min_pressure,
                                 station_daily.precip, station_daily.insolation)

    dayMonthDF = newdf.filter((newdf.dt_month == datetime_object.month) & (newdf.dt_day == datetime_object.day))
    statsDF = dayMonthDF.select(avg("max_temp").alias("max_temp"), avg("med_temp").alias("med_temp"),
                                avg("min_temp").alias("min_temp"),
                                avg("max_pressure").alias("max_pressure"), avg("min_pressure").alias("min_pressure"),
                                avg("precip").alias("precip"), avg("insolation").alias("insolation"))
    return statsDF


def predict(sql, sc, columns, station_id, currentWeather):
    columnsToPredict = ["max_temp", "med_temp", "min_temp", "max_pressure", "min_pressure", "precip", "insolation"]
    returnedPredictions = []

    # schema = StructType([])

    field = [StructField("station_id", StringType(), True),
             StructField("max_temp", FloatType(), True), \
             StructField("max_temp", FloatType(), True), \
             StructField("med_temp", FloatType(), True), \
             StructField("min_temp", FloatType(), True), \
             StructField("max_pressure", FloatType(), True), \
             StructField("min_pressure", FloatType(), True), \
             StructField("precip", FloatType(), True), \
             StructField("insolation", FloatType(), True), \
             StructField("prediction_max_temp", FloatType(), True), \
             StructField("prediction_max_temp", FloatType(), True), \
             StructField("prediction_med_temp", FloatType(), True), \
             StructField("prediction_min_temp", FloatType(), True), \
             StructField("prediction_max_pressure", FloatType(), True), \
             StructField("prediction_min_pressure", FloatType(), True), \
             StructField("prediction_precip", FloatType(), True), \
             StructField("prediction_insolation", FloatType(), True)]

    schema = StructType(field)

    resultDataframe = sql.createDataFrame(sc.emptyRDD(), schema)

    fields1 = [StructField("station_id", StringType(), True),
               StructField("max_temp", FloatType(), True), \
               StructField("med_temp", FloatType(), True), \
               StructField("min_temp", FloatType(), True), \
               StructField("max_pressure", FloatType(), True), \
               StructField("min_pressure", FloatType(), True), \
               StructField("precip", FloatType(), True), \
               StructField("insolation", FloatType(), True)]

    schema1 = StructType(fields1)

    resultDataframe = sql.createDataFrame(sc.emptyRDD(), schema)
    firstTime = True

    for column in columns:
        modelPath = "models/" + station_id + "__" + column
        if not os.path.exists(modelPath):
            logger.info("####No Model")
            break

        lrModel = LinearRegressionModel.load(modelPath)

        assembler = VectorAssembler(inputCols=[column], outputCol="features")

        df_for_predict = sql.createDataFrame([(currentWeather["station_id"],
											   float(currentWeather["max_temp"]),  # if column != "max_temp" else None,
                                               float(currentWeather["med_temp"]),  # if column != "med_temp" else None,
                                               float(currentWeather["min_temp"]),  # if column != "min_temp" else None,
                                               float(currentWeather["max_pres"]),  # if column != "max_pres" else None,
                                               float(currentWeather["min_pres"]),  # if column != "min_pres" else None,
                                               float(currentWeather["precip"]),  # if column != "precip" else None,
                                               float(currentWeather["insolation"]),
                                               # if column != "insolation" else None,
                                               )], schema1)

        assembledTestData = assembler.transform(df_for_predict)
        prediction_data = assembledTestData.withColumn("label", df_for_predict[column]).withColumn("features",
                                                                                                   assembledTestData.features)
        prediction_data1 = clearColumn(prediction_data, "label")

        predictions = lrModel.transform(prediction_data1, params={lrModel.intercept: True}).select("station_id", column,
                                                                                                   "prediction")
        predictions.show()

        predictions1 = predictions.withColumn(str("prediction_" + column), predictions.prediction)

        returnedPredictions.append(generalFunctions.dataframeToJson(predictions1))

    return json.dumps(returnedPredictions)


def clearColumn(dataframe, columnName):
    udf = UserDefinedFunction(lambda x: float(0), FloatType())
    new_df = dataframe.select(
        *[udf(column).alias(columnName) if column == columnName else column for column in dataframe.columns])
    return new_df


def getLimitsForStation(stations_limits, station_id):
    return stations_limits.filter(stations_limits.station_id == station_id)


def getLimitsAllStationsWithInterval(clean_daily, dateFrom, dateTo):
    datetime_object_from = datetime.strptime(dateFrom, '%Y-%m-%d').date()
    datetime_object_to = datetime.strptime(dateTo, '%Y-%m-%d').date()

    tmpDf = clean_daily.filter(
        (clean_daily.measure_date >= datetime_object_from) & (clean_daily.measure_date <= datetime_object_to))
    groupedDf = tmpDf.groupBy("station_id").agg(avg("max_temp"), avg("med_temp"), avg("min_temp"),
                                                avg("max_pressure"), avg("min_pressure"),
                                                avg("precip"), avg("insolation"))

    groupedDf.show()

    return groupedDf.select("station_id", "avg(max_temp)", "avg(med_temp)", "avg(min_temp)",
                            "avg(max_pressure)", "avg(min_pressure)", "avg(precip)", "avg(insolation)")


def getLimitsStationWithInterval(clean_daily, station_id, dateFrom, dateTo):
    datetime_object_from = datetime.strptime(dateFrom, '%Y-%m-%d').date()
    datetime_object_to = datetime.strptime(dateTo, '%Y-%m-%d').date()

    tmpDf = clean_daily.filter(
        (clean_daily.measure_date >= datetime_object_from) & (clean_daily.measure_date <= datetime_object_to) &
        (clean_daily.station_id == station_id))
    groupedDf = tmpDf.groupBy("station_id").agg(avg("max_temp"), avg("med_temp"), avg("min_temp"),
                                                avg("max_pressure"), avg("min_pressure"),
                                                avg("precip"), avg("insolation"))

    groupedDf.show()

    return groupedDf.select("station_id", "avg(max_temp)", "avg(med_temp)", "avg(min_temp)",
                            "avg(max_pressure)", "avg(min_pressure)", "avg(precip)", "avg(insolation)")