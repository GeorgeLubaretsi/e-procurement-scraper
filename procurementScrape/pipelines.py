# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/topics/item-pipeline.html
import json
import datetime
import os
from procurementScrape.items import Tender, Organisation, TenderBidder, TenderAgreement, TenderDocument
 
 
class ProcurementscrapePipeline(object):
    def __init__(self):
        
        self.startTime = datetime.datetime.now()
        nowStr = self.startTime.strftime("%Y-%m-%d %H:%M")
        if not os.path.exists("Scrapes"):
            os.makedirs("Scrapes")

        os.chdir("Scrapes")
        if not os.path.exists(nowStr):
            os.makedirs(nowStr)
            
        os.chdir(nowStr)
        
        self.tendersfile = open("tenders.json", 'wb')
        self.tendersfile.write("[")
        
        self.procuringEntitiesfile = open('organisations.json', 'wb')
        self.procuringEntitiesfile.write("[")
        
        self.tenderBiddersFile = open('tenderBidders.json', 'wb')
        self.tenderBiddersFile.write("[")
        
        self.tenderAgreementsFile = open('tenderAgreements.json', 'wb')
        self.tenderAgreementsFile.write("[")
         
        self.tenderDocumentationFile = open('tenderDocumentation.json', 'wb')
        self.tenderDocumentationFile.write("[")
        
        self.infoFile = open('scrapeInfo.txt', 'wb')
        self.infoFile.write("StartTime: " +nowStr+ "\n")
        
    def process_item(self, item, spider):
        line = json.dumps(dict(item)) + ","
        
        if isinstance(item, Tender):
            self.tendersfile.write(line)
        elif isinstance(item, Organisation):
            self.procuringEntitiesfile.write(line)
        elif isinstance(item, TenderBidder):
            self.tenderBiddersFile.write(line)
        elif isinstance(item, TenderAgreement):
            self.tenderAgreementsFile.write(line)
        elif isinstance(item, TenderDocument):
            self.tenderDocumentationFile.write(line)
        return item
    
    def close_spider(self,spider):
        self.endTime = datetime.datetime.now()
        endTimeStr = self.endTime.strftime("%Y-%m-%d %H:%M")
        self.infoFile.write("End Time: " +endTimeStr+ "\n")
        timeTaken = self.endTime - self.startTime
        
        minutes = int(timeTaken.seconds/60)
        seconds = timeTaken.seconds%60
        self.infoFile.write("Time Taken:    Days: %d    Minutes:    %d    Seconds    %d \n" % (timeTaken.days,minutes,seconds))
        self.infoFile.write("Records scraped: %d" % (spider.tenderCount))
        self.infoFile.close()
        
        self.tendersfile.write("]")
        self.tendersfile.close()
        
        self.procuringEntitiesfile.write("]")
        self.procuringEntitiesfile.close()
        
        self.tenderBiddersFile.write("]")
        self.tenderBiddersFile.close()
        
        self.tenderAgreementsFile.write("]")
        self.tenderAgreementsFile.close()
        
        self.tenderDocumentationFile.write("]")
        self.tenderAgreementsFile.close()
        

