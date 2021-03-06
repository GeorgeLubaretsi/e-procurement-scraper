#! /usr/bin/env python
#encoding:UTF-8


from scrapy.selector import HtmlXPathSelector
from scrapy.spider import BaseSpider
from scrapy.http import Request
from scrapy.utils.project import get_project_settings

import imp
items = imp.load_source('items', './procurementScrape/items.py')

from items import Tender, Organisation, TenderBidder, TenderAgreement, TenderDocument, CPVCode, WhiteListObject, BlackListObject, Complaint, BidderResult
import os
import sys
import httplib2
import shutil
from time import sleep

class ProcurementSpider(BaseSpider):
    name = "procurement"
    allowed_domains = ["procurement.gov.ge", "tenders.procurement.gov.ge"]
    baseUrl = "https://tenders.procurement.gov.ge/public/"
    mainPageBaseUrl = baseUrl+"lib/controller.php?action=search_app&page="

    baseListUrl = "http://procurement.gov.ge/index.php?lang_id=GEO"
    blackListUrl = "&sec_id=14&entrant="
    whiteListUrl = "&sec_id=62&entrant="
    blackListItemUrl = "&sec_id=14&info_id="
    whiteListItemUrl = "&sec_id=62&info_id="

    userAgent = 'Mozilla/5.0 (Windows; U; MSIE 9.0; WIndows NT 9.0; en-US'
    start_urls = [mainPageBaseUrl+"0"]
    tenderCount = 0
    orgCount = 0
    bidderCount = 0
    agreementCount = 0
    firstTender = 0
    docCount = 0
    failedRequests = []
   
    def make_requests_from_url(self, url):
        return Request(url, cookies=self.sessionCookies,headers={'User-Agent':'Mozilla/5.0 (Windows; U; MSIE 9.0; WIndows NT 9.0; en-US))'})
        
    def setSessionCookies(self,sessionCookie):
        self.sessionCookies = sessionCookie
        
    def setScrapeMode(self,scrapeMode):
        self.scrapeMode = scrapeMode
        
    def setScrapePath(self, path):
        self.scrapePath = path
        
    def parseResultsPage(self,response):
        hxs = HtmlXPathSelector(response)
        resultsDividersXPath = hxs.select('//div[contains(@id, "agency_docs")]//div')
        resultsDividers = resultsDividersXPath.extract()
     
        
        #get results documents      
        if resultsDividers.__len__() >= 2:
            winnerDiv = resultsDividers[1]
            tenderID = response.meta['tenderID']

            #parse results section if there is one
            if winnerDiv.find(u"ხელშეკრულება") > -1:    
              amendmentNumber = 0
              item = TenderAgreement()
              item["tenderID"] = tenderID
              item["AmendmentNumber"] = str(amendmentNumber)
              
              index = winnerDiv.find("ShowProfile")
              index = winnerDiv.find("(",index)
              endIndex = winnerDiv.find(")",index)
              
              orgUrl = winnerDiv[index+1:endIndex]
              item["OrgUrl"] = orgUrl
                      
              index = winnerDiv.find(u"ნომერი/თანხა")
              endIndex = winnerDiv.find("<br",index)
              index = winnerDiv.rfind("/",index,endIndex)
              item["Amount"] = winnerDiv[index+1:endIndex].strip()
              
              #there seem to be 2 different types of agreement date types
              #one has a single Contract validity date and the other has a start and end date
              dateRange = winnerDiv.find("-",index)
              if dateRange > -1:
                index = winnerDiv.find(u"ძალაშია",index)
                index = winnerDiv.find(":",index)
                endIndex = winnerDiv.find("-",index)
                item["StartDate"] = winnerDiv[index+1:endIndex].strip()
                
                index = endIndex
                endIndex = winnerDiv.find("<",index)
                item["ExpiryDate"] = winnerDiv[index+1:endIndex].strip()
              else:
                index = winnerDiv.find("date",validityIndex)
                index = winnerDiv.find(">",index)
                endIndex = winnerDiv.find("</",index)
                item["ExpiryDate"] = winnerDiv[index+1:endIndex].strip()

              
              #find the document download section
              index = winnerDiv.find('align="right',index)
              index = winnerDiv.find("href",index)
              index = winnerDiv.find('"',index)+1
              endIndex = winnerDiv.find('"',index)
              item["documentUrl"] = self.baseUrl+winnerDiv[index:endIndex]

              self.agreementCount = self.agreementCount + 1
              yield item
            
              #check for contract amendment
              if resultsDividers.__len__() > 2:
                count = 0
                for divider in resultsDividers:
                  if count < 2:
                    count = count + 1
                    continue
                  xAmendmentsTable = resultsDividersXPath[count]
                  xAmendments = xAmendmentsTable.select('.//tr')               
                  item = TenderAgreement()
                  item["tenderID"] = tenderID
                  #agreement change
                  if divider.find(u"ხელშეკრულების ცვლილება") > -1 or divider.find(u"ხელშეკრულებაში შეცდომის გასწორება") > -1: 
                    #extract all rows
                    for row in xAmendments:
                      amendmentHtml = row.extract()                
                      amendmentNumber = amendmentNumber + 1
                      item["AmendmentNumber"] = str(amendmentNumber)
                      #should be the same org as the original contract
                      item["OrgUrl"] = orgUrl
                      self.agreementCount = self.agreementCount + 1
                      index = amendmentHtml.find(u"ნომერი/თანხა")
                      endIndex = amendmentHtml.find("<br",index)
                      index = amendmentHtml.rfind("/",index,endIndex)
                      item["Amount"] = amendmentHtml[index+1:endIndex].strip()
                      
                      index = amendmentHtml.find(u"ძალაშია",index)
                      index = amendmentHtml.find(":",index)
                      endIndex = amendmentHtml.find("-",index)
                      item["StartDate"] = amendmentHtml[index+1:endIndex].strip()
                      
                      index = endIndex
                      endIndex = amendmentHtml.find("<",index)
                      item["ExpiryDate"] = amendmentHtml[index+1:endIndex].strip()
                                         
                      #error correction
                      if divider.find(u"ხელშეკრულებაში შეცდომის გასწორება") > -1:
                        item["documentUrl"] = "Treaty Correction: No Document"
                      else:
                        index = amendmentHtml.find('align="right',index)
                        index = amendmentHtml.find("href",index)
                        index = amendmentHtml.find('"',index)+1
                        endIndex = amendmentHtml.find('"',index)
                        item["documentUrl"] = self.baseUrl+amendmentHtml[index:endIndex].strip()
                      yield item
                  
                  #disqualify (might be another company so the contract is still valid)
                  elif divider.find(u"დისკვალიფიკაცია") > -1 or divider.find(u"პრეტენდენტმა უარი თქვა წინადადებაზე") > -1:        
                    #extract all rows
                    for row in xAmendments:
                      amendmentHtml = row.extract()                    
                      index = amendmentHtml.find("width")
                      index = amendmentHtml.find(">",index)
                      endIndex = amendmentHtml.find("</",index) 
                      item["StartDate"] = amendmentHtml[index+1:endIndex].strip()

                      index = amendmentHtml.find("strong",index)
                      index = amendmentHtml.find(">",index)
                      endIndex = amendmentHtml.find("</",index)
                      item["OrgUrl"] = amendmentHtml[index+1:endIndex].strip()
                   
                      item["Amount"] = "NULL"
                      item["StartDate"] = "NULL"                                 
                      item["ExpiryDate"] = "NULL"
                   
                      if divider.find(u"დისკვალიფიკაცია") > -1:
                        item["documentUrl"] = "disqualified"
                      else:
                        item["documentUrl"] = "bidder refused agreement"
                      
                      yield item
                  #unknown stuff
                  else:
                    item = TenderAgreement()
                    item["tenderID"] = tenderID
                    item["AmendmentNumber"] = str(0)
                    item["Amount"] = "-1"                             
                    item["StartDate"] = "NULL"                            
                    item["documentUrl"] = "unknown"
                    item["OrgUrl"] = "NULL"
                    item["ExpiryDate"] = "NULL"
                    yield item
                  count = count + 1
               
    def parseBidsPage(self,response):
        #print "parsing bids"
        hxs = HtmlXPathSelector(response)
        bidRows = hxs.select('//div[contains(@id, "app_bids")]//table[last()]/tbody//tr').extract()
        if bidRows.__len__() == 0:
            return
        for bidder in bidRows:
            item = TenderBidder()
            self.bidderCount = self.bidderCount + 1
            item["tenderID"] = response.meta['tenderID']
            index = bidder.find("ShowProfile")
            index = bidder.find("(",index)
            endIndex = bidder.find(")",index)
            item["OrgUrl"] = bidder[index+1:endIndex]
    
            index = bidder.find("strong")
            index = bidder.find(">",index)
            endIndex = bidder.find("<",index)
            item["lastBidAmount"] = bidder[index+1:endIndex].strip().replace("`","").strip()
            
            index = bidder.find("date",index)
            index = bidder.find(">",index)
            endIndex = bidder.find("<",index)
            item["lastBidDate"] = bidder[index+1:endIndex].strip()
            
            index = bidder.find("activebid",index)
            index = bidder.find(">",index)
            endIndex = bidder.find("<",index)
            item["firstBidAmount"] = bidder[index+1:endIndex-1].strip().replace("`","").strip()
            
            index = bidder.find("date",index)
            index = bidder.find(">",index)
            endIndex = bidder.find("<",index)
            item["firstBidDate"] = bidder[index+1:endIndex].strip()
            
            index = bidder.find('align="center"',index)
            index = bidder.find("[",index)
            endIndex = bidder.find("]",index)
            item["numberOfBids"] = bidder[index+1:endIndex].strip()
            
            yield item
            
            #now lets use the company id to scrape the company data
            url = self.baseUrl+"lib/controller.php?action=profile&org_id="+item['OrgUrl']
            metaData = { 'OrgUrl': item['OrgUrl'], 'type': "biddingOrg"}
            organisation_request = Request(url, meta=metaData,errback=self.orgFailed, callback=self.parseOrganisation, cookies=self.sessionCookies, dont_filter=True, headers={"User-Agent":self.userAgent})

            yield organisation_request
    
    def parseDocumentationPage(self,response):
        hxs = HtmlXPathSelector(response)
        documentRows = hxs.select('//table[contains(@id, "tender_docs")]//tr').extract()
        #drop element 0
        documentRows.pop(0)
        for documentRow in documentRows:
            item = TenderDocument()
            
            item["tenderID"] = response.meta['tenderID']
            
            index = documentRow.find("id")
            index = documentRow.find('"',index) + 1
            endIndex = documentRow.find('"',index)
            rawData = documentRow[index:endIndex]
            dataArray = rawData.split(".")
            url = self.baseUrl+"lib/files.php?mode=app&"
            item["documentUrl"] = url+"file="+dataArray[0]+"&code="+dataArray[1]

            index = documentRow.find("obsolete",index)
            index = documentRow.find("<",index)
            index = documentRow.find(">",index)
            
            endIndex = documentRow.find("</",index)
            item["title"] = documentRow[index+1:endIndex].strip()
            
            index = documentRow.find("date",endIndex)
            index = documentRow.find(">",index)
            endIndex = documentRow.find(":",index)
            item["date"] = documentRow[index+1:endIndex].strip()
            
            index = documentRow.find(":",endIndex+1)
            endIndex = documentRow.find("</td",index)
            item["author"] = documentRow[index+1:endIndex].strip()
            self.docCount = self.docCount + 1

            yield item
        
    
    def parseOrganisation(self,response):
        self.orgCount = self.orgCount + 1
        #print "parsing procurer"
        hxs = HtmlXPathSelector(response)
        keyPairs = hxs.select('//div[contains(@id, "profile_dialog")]//tr').extract()
        item = Organisation()
        item["OrgUrl"] = response.meta['OrgUrl']

        index = keyPairs[0].find("label")
        index = keyPairs[0].find(">",index)
        endIndex = keyPairs[0].find("<",index)
        item["Type"] = keyPairs[0][index+1:endIndex].strip()
        
        index = keyPairs[0].find("strong",index)
        index = keyPairs[0].find(">",index)
        endIndex = keyPairs[0].find("<",index)
        item["Name"] = keyPairs[0][index+1:endIndex].strip()
        
        index = keyPairs[1].find("/td")
        index = keyPairs[1].find("<td",index)
        index = keyPairs[1].find(">",index)
        endIndex = keyPairs[1].find("<",index)
        item["OrgID"] = keyPairs[1][index+1:endIndex]
        #print "parsing Org: " + item['OrgUrl'] +" OrgID: "+ item['OrgID']
        
        index = keyPairs[2].find("/td")
        index = keyPairs[2].find("<td",index)
        index = keyPairs[2].find(">",index)
        endIndex = keyPairs[2].find("<",index)
        item["Country"] = keyPairs[2][index+1:endIndex].strip()
        
        index = keyPairs[3].find("/td")
        index = keyPairs[3].find("<td",index)
        index = keyPairs[3].find(">",index)
        endIndex = keyPairs[3].find("<",index)
        item["city"] = keyPairs[3][index+1:endIndex].strip()
        
        index = keyPairs[4].find("/td")
        index = keyPairs[4].find("<td",index)
        index = keyPairs[4].find(">",index)
        endIndex = keyPairs[4].find("<",index)
        item["address"] = keyPairs[4][index+1:endIndex].strip()
        
        index = keyPairs[5].find("/td")
        index = keyPairs[5].find("<td",index)
        index = keyPairs[5].find(">",index)
        endIndex = keyPairs[5].find("<",index)
        item["phoneNumber"] = keyPairs[5][index+1:endIndex].strip()
        
        index = keyPairs[6].find("/td")
        index = keyPairs[6].find("<td",index)
        index = keyPairs[6].find(">",index)
        endIndex = keyPairs[6].find("<",index)
        item["faxNumber"] = keyPairs[6][index+1:endIndex].strip()
        
        #dig into 'a' tag
        index = keyPairs[7].find("href")
        index = keyPairs[7].find(">",index)
        endIndex = keyPairs[7].find("<",index)
        item["email"] = keyPairs[7][index+1:endIndex].strip()

        #dig into 'a' tag
        index = keyPairs[8].find("href")
        index = keyPairs[8].find(">",index)
        endIndex = keyPairs[8].find("<",index)
        item["webpage"] = keyPairs[8] [index+1:endIndex].strip()
        
        yield item

    def xstr(self, s):
        if s is None:
            return ''
        return s

    def findKeyValue(self, keyString, pairs, conditions, direction = 1 ):
        keyCondition = (keyString, )
        result = self.findData( pairs, keyCondition, -1 )
        if result[0] is not None:
            result = self.findData( pairs, conditions, result[1]+direction )
        return self.xstr(result[0])

    def findData(self, keypairs, conditionList, startPair ):
        result = [None, -1]
        for i, keyPair in enumerate(keypairs):       
            if i >= startPair:        
                index = 0
                prevIndex = -1
                found = True
                #I make the assumption that the 2nd last index I calculate will be the start of substring
                #and the last index is the end of the substring so I need to always keep track of the 2nd last index
                for condition in conditionList:
                    searchIndex = keyPair.find(condition,index)
                    if searchIndex == -1:
                        found = False
                        break;
                    prevIndex = index
                    index = searchIndex
                if found:
                    result[0] = keyPair[prevIndex+1:index]
                    result[1] = i
                    return result
        return result
    
    def parseTender(self, response):
        self.tenderCount = self.tenderCount + 1
        hxs = HtmlXPathSelector(response)
        keyPairs = hxs.select('//tr/td').extract()
        toYield = []
        item = Tender()
     
        item['tenderID'] = response.meta['tenderUrl']
        conditions = "ShowProfile","(", ")"
        result = self.findData( keyPairs, conditions, -1 )
        item['procuringEntityUrl'] = result[0].strip()
        
        conditions = "<img", ">", "</"
        result = self.findData( keyPairs, conditions, result[1] )
        item['procuringEntityName'] = result[0].strip()
        
        conditions = ">","<"
        item['tenderType'] = self.findKeyValue( u"შესყიდვის ტიპი", keyPairs, conditions ).strip()
        
        conditions = "strong",">","<"
        item['tenderRegistrationNumber']  = self.findKeyValue( u"განცხადების ნომერი", keyPairs, conditions ).strip()

        conditions =  "img",">","<"
        tenderStatusValue = self.findKeyValue( u"შესყიდვის მიმდინარეობის სტატუსი", keyPairs, conditions )
        if tenderStatusValue is None or len(tenderStatusValue) == 0:
            item['tenderStatus']  = self.findKeyValue( u"შესყიდვის სტატუსი", keyPairs, conditions ).strip()
        else:
            item['tenderStatus']  = tenderStatusValue.strip()
        
        conditions = ">","<"
        item['tenderAnnouncementDate'] =   self.findKeyValue( u"შესყიდვის გამოცხადების თარიღი", keyPairs, conditions ).strip()
        item['bidsStartDate'] =  self.findKeyValue( u"წინადადებების მიღება იწყება", keyPairs, conditions ).strip()     
        item['bidsEndDate'] =  self.findKeyValue( u"წინადადებების მიღება მთავრდება", keyPairs, conditions ).strip()
        
        conditions = "span", ">", "<"
        val =  self.findKeyValue( u"შესყიდვის სავარაუდო ღირებულება", keyPairs, conditions )
        if val == None:
          val =  self.findKeyValue( u"პრეისკურანტის სავარაუდო ღირებულება", keyPairs, conditions )
        item['estimatedValue'] = val.replace("`","").replace("GEL","").strip()

        conditions = "/strong",">","<"
        item['cpvCode'] =  self.findKeyValue( u"შესყიდვის კატეგორია", keyPairs, conditions ).strip()
      
        conditions = "blabla",">","</"
        item['info'] =  self.findKeyValue( u"დამატებითი ინფორმაცია", keyPairs, conditions ).strip()
        
        conditions = ">","</"
        item['amountToSupply'] =  self.findKeyValue( u"შესყიდვის რაოდენობა ან მოცულობა", keyPairs, conditions ).strip()
        item['supplyPeriod'] =  self.findKeyValue( u"მოწოდების ვადა", keyPairs, conditions ).strip()
        item['offerStep'] =  self.findKeyValue( u"შეთავაზების ფასის კლების ბიჯი", keyPairs, conditions ).strip()
        guaranteeAmountVal = self.findKeyValue( u"გარანტიის ოდენობა", keyPairs, conditions )
        if guaranteeAmountVal is not None:
            item['guaranteeAmount'] =  guaranteeAmountVal.strip()
        else:
            item['guaranteeAmount'] = ""

        period = self.findKeyValue( u"გარანტიის მოქმედების ვადა", keyPairs, conditions )
        if period is not None:
          item['guaranteePeriod'] = period.strip()
        else:
          item['guaranteePeriod'] = "NO"
          
        toYield.append(item)

        #the sub cpv codes are within a list so we will deal with these seperately

        #get all list items within a div tag
        cpvItems = hxs.select('//div/ul/li').extract()

        for cpvItem in cpvItems:
          if cpvItem.find("padding:4px") > -1:
            startIndex = cpvItem.find(">")
            endIndex = cpvItem.find("-",startIndex)
            cpvCode = cpvItem[startIndex+6:endIndex]
            descriptionEnd = cpvItem.find("<div",endIndex)
            description = cpvItem[endIndex+1:descriptionEnd]
            cpvObject = CPVCode()
            cpvObject['tenderID'] = item['tenderID']
            cpvObject['cpvCode'] = cpvCode.strip()
            cpvObject['description'] = description.strip()
            toYield.append(cpvObject)
            
    
        #now lets use the procuring entity id to find more info about the procurer
        print "parsing Tender: " + item['tenderID'] +" procurerURL: "+ item['procuringEntityUrl']
        url = self.baseUrl+"lib/controller.php?action=profile&org_id="+item['procuringEntityUrl']
        metaData = {'OrgUrl': item['procuringEntityUrl'],'type': "procuringOrg"}
        procurer_request = Request(url, errback=self.orgFailed, meta=metaData, callback=self.parseOrganisation, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        toYield.append(procurer_request)     

        #now lets look at the tender documentation
        url = self.baseUrl+"lib/controller.php?action=app_docs&app_id="+item['tenderID']
        print "parsing Tender Documentation"
        print url
        documentation_request = Request(url, errback=self.documentationFailed,callback=self.parseDocumentationPage, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        documentation_request.meta['tenderID'] = item['tenderID']
        toYield.append(documentation_request)   
        
        #now lets look at the bids made on this tender
        url = self.baseUrl+"lib/controller.php?action=app_bids&app_id="+item['tenderID']
        print "parsing Tender Bids"
        print url
        bids_request = Request(url, errback=self.bidsFailed,callback=self.parseBidsPage, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        bids_request.meta['tenderID'] = item['tenderID']
        toYield.append(bids_request)   
        
        #finally lets look at the results of this tender
        url = self.baseUrl+"lib/controller.php?action=agency_docs&app_id="+item['tenderID']
        print "parsing Tender result"
        print url
        results_request = Request(url, errback=self.resultFailed,callback=self.parseResultsPage,cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        results_request.meta['tenderID'] = item['tenderID']
        toYield.append(results_request)   
  
        return toYield
        
    def parseTenderUrls(self, response):
        hxs = HtmlXPathSelector(response)
        
        tenderOnClickItems = hxs.select('//table[@id="list_apps_by_subject"]//tr//@onclick').extract()
        print "processing page: " + response.url
        first = True
        page = response.meta['page']
        incrementalFinished = False
        for tenderOnClickItem in tenderOnClickItems:
            base_tender_url = self.baseUrl+"lib/controller.php?action=app_main&app_id="
            index = tenderOnClickItem.find("ShowApp")
            index = tenderOnClickItem.find("(",index)
            endIndex = tenderOnClickItem.find(",",index)
            index_url = tenderOnClickItem[index+1:endIndex]
            if self.scrapeMode == "INCREMENTAL":
                if index_url == response.meta['prevScrapeStartTender']:
                    incrementalFinished = True
                    break
            tender_url = base_tender_url+index_url
            request = Request(tender_url, errback=self.tenderFailed,callback=self.parseTender, cookies=self.sessionCookies, meta={"tenderUrl": index_url, "prevScrapeStartTender": response.meta['prevScrapeStartTender']},headers={"User-Agent":self.userAgent})
            
            #if this is the first page store the first tender as a marker so the incremental scraper knows where to stop.
            if page == 1 and first:
              self.firstTender = index_url
            first = False
            yield request
            
        if not incrementalFinished and page < int(response.meta['final_page']):
            page = page+1
            url = self.mainPageBaseUrl+str(page)
            metadata ={"page": page, "final_page": response.meta['final_page'], "prevScrapeStartTender": response.meta['prevScrapeStartTender']}
            print "parse tender urls"
            print url
            request = Request(url, errback=self.urlPageFailed,callback=self.parseTenderUrls, meta=metadata, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
            yield request


    def parseWhiteListItem(self, response):
      hxs = HtmlXPathSelector(response)
      nameDiv = hxs.select('//div[@class="txt_page"]//div[@class="name"]').extract()[0]
      dateDiv = hxs.select('//div[@class="txt_page"]//div[@class="indate"]').extract()[0]
      infoDivs = hxs.select('//div[@class="txt_page"]//div[@class="txt"]//a').extract()
      listDocumentDiv = infoDivs[0]
      companyDocDiv = infoDivs[1]

      startIndex = nameDiv.find(">")
      endIndex = nameDiv.find("(",startIndex)
      name = nameDiv[startIndex+1:endIndex]

      startIndex = nameDiv.find(":",endIndex)
      endIndex = nameDiv.find(")",startIndex)
      orgID = nameDiv[startIndex+1:endIndex]

      startIndex = dateDiv.find(">")
      startIndex = dateDiv.find(":",startIndex)
      endIndex = dateDiv.find("<",startIndex)
      date = dateDiv[startIndex+1:endIndex]

      startIndex = listDocumentDiv.find("href")
      startIndex = listDocumentDiv.find("=",startIndex)
      endIndex = listDocumentDiv.find("target",startIndex)
      listDocumentUrl = listDocumentDiv[startIndex+1:endIndex]

      startIndex = companyDocDiv.find("href")
      startIndex = companyDocDiv.find("=",startIndex)
      endIndex = companyDocDiv.find("target",startIndex)
      companyDocUrl = companyDocDiv[startIndex+1:endIndex]

      item = WhiteListObject()
      item['orgID'] = orgID.strip()
      item['orgName'] = name.strip()
      item['issueDate'] = date.strip()
      item['agreementUrl'] = listDocumentUrl.strip()
      item['companyInfoUrl'] = companyDocUrl.strip()
      yield item   

    def parseBlackListItem(self, response):
      hxs = HtmlXPathSelector(response)
      nameDiv = hxs.select('//div[@class="txt_page"]//div[@class="name"]').extract()[0]
      dateDiv = hxs.select('//div[@class="txt_page"]//div[@class="indate"]').extract()[0]
      info = hxs.select('//div[@class="txt_page"]//div[@class="txt"]').extract()[0]
      count = 0
      found = False

      startIndex = nameDiv.find(">")
      endIndex = nameDiv.find("(",startIndex)
      name = nameDiv[startIndex+1:endIndex]
      startIndex = nameDiv.find(":",endIndex)
      endIndex = nameDiv.find(")",startIndex)
      orgID = nameDiv[startIndex+1:endIndex]

      startIndex = dateDiv.find(">")
      startIndex = dateDiv.find(":",startIndex)
      endIndex = dateDiv.find("<",startIndex)
      date = dateDiv[startIndex+1:endIndex]

      startIndex = info.find(u"ორგანიზაცია")
      startIndex = info.find(":",startIndex)
      endIndex = info.find(";",startIndex)
      procurer = info[startIndex+1:endIndex]

      tenderNum = "NULL"
      tenderSearchStr = "SPA"
      #to fix a data entry bug on the procurement side
      if info.find(u"შPA") > -1:
        tenderSearchStr = u"შPA"
      startIndex = info.find(tenderSearchStr)
      if startIndex == -1:
        tenderID = "NULL"
        startIndex = info.find(u"№")
        endIndex = info.find(";",startIndex)
        if startIndex == -1:
          tenderNum = info[startIndex:endIndex]
      else:
        finished = False
        tenderID = ""
        found = True
        while found:
          startIndex = info.find(tenderSearchStr,startIndex)
          if startIndex == -1:
            break
          endIndex = info.find("</a",startIndex)
          spaID = info[startIndex:endIndex].replace(u"შ","S")
          tenderID += spaID + ","
          startIndex = endIndex

      startIndex = info.find(u"შავ სიაში რეგისტრაციის მიზეზი")
      startIndex = info.find(":",startIndex)
      endIndex = info.find("<",startIndex)
      reason = info[startIndex+1:endIndex]

      item = BlackListObject()
      item['orgID'] = orgID.strip()
      item['orgName'] = name.strip()
      item['issueDate'] = date.strip()
      item['procurer'] = procurer.strip()
      item['tenderID'] = tenderID.strip()
      item['tenderNum'] = tenderNum.strip()
      item['reason'] = reason.strip()
      yield item  
   

    def parseWhiteListUrls(self, response):
      hxs = HtmlXPathSelector(response)
      print "Parsing White List Page" + str(response.meta["page"])
      #find last page if needed
      final_page = response.meta["final_page"]
      if final_page == -1:
        pageLinks = hxs.select('//div[@class="pager"]//a').extract()
        lastLink = pageLinks[-1]
        startIndex = lastLink.find("entrant")
        startIndex = lastLink.find("=",startIndex)
        endIndex = lastLink.find('&',startIndex)
        final_page = int(lastLink[startIndex+1:endIndex])
   
      whiteListLinks = hxs.select('//div[@class="right_block_cont"]//div[@class="right_block_text"]//a').extract()
      #generate requests for each link
      for link in whiteListLinks:
        startIndex = link.find("info_id")
        startIndex = link.find("=",startIndex)
        endIndex = link.find(">",startIndex)
        itemID = link[startIndex+1:endIndex-1]
        url = self.baseListUrl+self.whiteListItemUrl+str(itemID)
        request = Request(url,callback=self.parseWhiteListItem, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        yield request
        
      #yield a new request to get the next page
      nextPage = response.meta["page"] + 1
      if nextPage <= final_page:
        metadata = {"page" : nextPage, "final_page" : final_page}
        url = self.baseListUrl+self.whiteListUrl+str(nextPage)
        request = Request(url,callback=self.parseWhiteListUrls, meta = metadata, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        yield request    

    def parseBlackListUrls(self, response):
      hxs = HtmlXPathSelector(response)
      print "Parsing Black List Page " + str(response.meta["page"])
      #find last page if needed
      final_page = response.meta["final_page"]
      if final_page == -1:
        pageLinks = hxs.select('//div[@class="pager"]//a').extract()
        lastLink = pageLinks[-1]
        startIndex = lastLink.find("entrant")
        startIndex = lastLink.find("=",startIndex)
        endIndex = lastLink.find('&',startIndex)
        final_page = int(lastLink[startIndex+1:endIndex])
   
      blackListLinks = hxs.select('//div[@class="right_block_cont"]//div[@class="right_block_text"]//a').extract()
      for link in blackListLinks:
        startIndex = link.find("info_id")
        startIndex = link.find("=",startIndex)
        endIndex = link.find(">",startIndex)
        itemID = link[startIndex+1:endIndex-1]
        url = self.baseListUrl+self.blackListItemUrl+str(itemID)
        request = Request(url,callback=self.parseBlackListItem, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        yield request
        
      #yield a new request to get the next page
      nextPage = response.meta["page"] + 1
      if nextPage <= final_page:
        metadata = {"page" : nextPage, "final_page" : final_page}
        url = self.baseListUrl+self.blackListUrl+str(nextPage)
        request = Request(url,callback=self.parseBlackListUrls, meta = metadata, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        yield request 

    def getDataByLabel(self, label, divs ):
      count = 0
      dataIndex = -1
      for div in divs:   
        if div.find(label) > -1:
          dataIndex = count + 1
          break
        count += 1
      if dataIndex == -1:
        return NULL
      else:
        return divs[dataIndex]

    def parseDispute(self, response):
      hxs = HtmlXPathSelector(response)
      divs = hxs.select('//div[@class="claim ui-corner-all"]//div').extract()
      lastClaimDiv = hxs.select('//div[@class="claim ui-corner-all"]').extract()[-1]

      item = Complaint()

      statusDiv = self.getDataByLabel(u"საჩივრის მიმდინარე სტატუსი",divs)
      startIndex = statusDiv.find("img")
      startIndex = statusDiv.find(">",startIndex)
      endIndex = statusDiv.find("</",startIndex)
      item["status"] = statusDiv[startIndex+1:endIndex]

      organizationDiv = self.getDataByLabel(u"მომჩივანი",divs)
      startIndex = organizationDiv.find("strong>")
      startIndex = organizationDiv.find(">",startIndex)
      endIndex = organizationDiv.find("</")
      item["orgName"] = organizationDiv[startIndex+1:endIndex]

      startIndex = organizationDiv.find("(",startIndex)
      endIndex = organizationDiv.find(")",startIndex)
      item["orgID"] = organizationDiv[startIndex+1:endIndex]

      tenderDiv = self.getDataByLabel(u"სადავო",divs)
      startIndex = tenderDiv.find("strong>")
      startIndex = tenderDiv.find(">",startIndex)
      endIndex = tenderDiv.find("</",startIndex)
      item["tenderID"] = tenderDiv[startIndex+1:endIndex]

      complaintDiv = self.getDataByLabel(u"საჩივრის არსი",divs)
      startIndex = complaintDiv.find(">")
      endIndex = complaintDiv.find("</")
      item["complaint"] = complaintDiv[startIndex+1:endIndex]

      legalBasisDiv = self.getDataByLabel(u"საჩივრის სამართლებრივი საფუძვლები",divs)
      startIndex = legalBasisDiv.find("<li>")
      startIndex = legalBasisDiv.find("</div",startIndex)
      startIndex = legalBasisDiv.find(">",startIndex)
      endIndex = legalBasisDiv.find("</li",startIndex)
      item["legalBasis"] = legalBasisDiv[startIndex+1:endIndex]

      demandDiv = self.getDataByLabel(u"მოთხოვნა",divs)
      startIndex = demandDiv.find(">")
      endIndex = demandDiv.find("</",startIndex)
      item["demand"] = demandDiv[startIndex+1:endIndex]

      startIndex = lastClaimDiv.find(u"სტატუსების ისტორია")
      endIndex = lastClaimDiv.find(u"საჩივარი შემოსულია", startIndex)
      endIndex = lastClaimDiv.rfind("</td",startIndex,endIndex)
      startIndex = lastClaimDiv.rfind("<td",startIndex,endIndex)
      startIndex = lastClaimDiv.find(">",startIndex,endIndex)
      item["issueDate"] = lastClaimDiv[startIndex+1:endIndex]
      
      yield item

    def parseDisputeLinks(self, response):
      hxs = HtmlXPathSelector(response)
      disputeLinks = hxs.select('//td[@title]').extract()
      #get disputeID
      for link in disputeLinks:
        startIndex = link.find("=")
        endIndex = link.find(">")
        linkID = link[startIndex+1:endIndex]
        linkID = linkID.replace('"','')
        url = "https://tenders.procurement.gov.ge/dispute/engine/controller.php?action=showapp&app_id="+linkID
        print url
        request = Request(url,callback=self.parseDispute, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        yield request

    def getLastScrapedTender(self):
      #find where the last scrape left off
      scrapeList = []
      currentDir = os.getcwd()
      if os.path.exists("FullScrapes"):
          fullScrapes = os.listdir("FullScrapes")
          
      if os.path.exists("IncrementalScrapes"):
          incrementalScrapes = os.listdir("IncrementalScrapes")
      scrapeList = fullScrapes + incrementalScrapes
      #now we have a list of old scrape directories lets find the most recent one and find the first tender it scraped
      scrapeList.sort()
      lastTenderURL = -1
      while lastTenderURL == -1 and scrapeList.count > 0:
          last = scrapeList.pop()
          typeDir = "IncrementalScrapes"
          if fullScrapes.__contains__(last):
              typeDir = "FullScrapes"
              
          lastScrapeInfo = open(currentDir+"/"+typeDir+"/"+last+"/"+"scrapeInfo.txt")
          
          while 1:
              line = lastScrapeInfo.readline()
              if not line:
                  break
              index = line.find("firstTenderURL")
              if index > -1:
                  index = line.find(":")
                  lastTenderURL = line[index+2:]
                  break
      return lastTenderURL   

    #spider start point
    def parse(self, response):
      #if we are fixing errors from a previous scrape
      if self.scrapeMode == "FIXERRORS":
        self.firstTender = -1
        tender_url = "action=app_main&app_id="
        org_url = "action=profile&org_id="
        bidder_url = "action=app_bids&app_id="
        agreement_url = "action=agency_docs&app_id="
        document_url = "action=app_docs&app_id=" 

        failPath = self.fixpath+"/failures.txt"
        failFile = open(failPath, 'r')
        for item_url in failFile:
          if item_url.find(tender_url) > -1:
            index = item_url.find("app_id")
            index = item_url.find("=",index)  
            index_url = item_url[index+1:]
            request = Request(item_url, errback=self.tenderFailed,callback=self.parseTender, cookies=self.sessionCookies, meta={"tenderUrl": index_url},headers={"User-Agent":self.userAgent})
            print "tender: "+item_url
            yield request
          elif item_url.find(org_url) > -1:
            index = item_url.find("org_id")
            index = item_url.find("=",index)
            org_url = item_url[index+1:]
            metaData = {'OrgUrl': org_url,'type': "procuringOrg"}
            request = Request(item_url, errback=self.orgFailed, meta=metaData, callback=self.parseOrganisation, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
            print "org: "+org_url
            yield request
          elif item_url.find(bidder_url) > -1:
            index = item_url.find("app_id")
            index = item_url.find("=",index)
            tender_id = item_url[index+1:]
            request = Request(item_url, errback=self.bidsFailed,callback=self.parseBidsPage, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
            request.meta['tenderID'] = tender_id
            print "bid: "+tender_id
            yield request
          elif item_url.find(agreement_url) > -1:
            index = item_url.find("app_id")
            index = item_url.find("=",index)
            tender_id = item_url[index+1:]
            request = Request(item_url, errback=self.resultFailed,callback=self.parseResultsPage,cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
            request.meta['tenderID'] = tender_id
            print "agree: "+tender_id
            yield request
          elif item_url.find(document_url) > -1:
            index = item_url.find("app_id")
            index = item_url.find("=",index)
            tender_id = item_url[index+1:]
            documentation_request = Request(item_url, errback=self.documentationFailed,callback=self.parseDocumentationPage, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
            documentation_request.meta['tenderID'] = tender_id
            print "doc: "+tender_id
            yield request 
        failFile.close()
          
        
      #if we are doing a single tender test scrape
      elif self.scrapeMode == "SINGLE":
        url_id = self.scrapeMode
        tender_url = self.baseUrl+"lib/controller.php?action=app_main&app_id="+url_id
        self.firstTender = self.scrapeMode
        request = Request(tender_url, errback=self.tenderFailed,callback=self.parseTender, cookies=self.sessionCookies, meta={"tenderUrl": url_id},headers={"User-Agent":self.userAgent})
        yield request
                  
      else:  
        #Find index of last page
        hxs = HtmlXPathSelector(response)
        totalPagesButton = hxs.select('//div[@class="pager pad4px"]//button').extract()[2]
        
        index = totalPagesButton.find('/')
        endIndex = totalPagesButton.find(')',index)
        final_page = totalPagesButton[index+1:endIndex]
        
        if( final_page == -1 ):
            #print "Parsing Error... stopping"
            return
        
        lastTenderURL = -1
        if self.scrapeMode == "INCREMENTAL":
          lastTenderURL = self.getLastScrapedTender()

        print "Starting scrape"
        startPage = 1
        url = self.mainPageBaseUrl+str(startPage)
        print "parse function"
        print url
        metadata = {"page": startPage, "final_page": final_page, "prevScrapeStartTender": lastTenderURL}
        request = Request(url, errback=self.urlPageFailed,callback=self.parseTenderUrls, meta = metadata, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        print "url: " + url
        yield request
      
        #now that we have queued up the scrape to find new tenders lets go through our inProgress list and scrape for updates
        if self.scrapeMode == "INCREMENTAL":
          updatesFile = open(self.tenderUpdatesFile, 'r')
          for url_id in updatesFile:
            item_url = self.baseUrl+"lib/controller.php?action=app_main&app_id="+url_id.replace("\n","")
            request = Request(item_url, errback=self.tenderFailed,callback=self.parseTender, cookies=self.sessionCookies, meta={"tenderUrl": url_id},headers={"User-Agent":self.userAgent})
            yield request
   
        #parse white/black/disputes lists
        metadata = {"page" : 1, "final_page" : -1}
        print "scraping white list"
        url = self.baseListUrl+self.whiteListUrl+str(1)
        request = Request(url,callback=self.parseWhiteListUrls, meta = metadata, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})     
        yield request
                
        print "scraping black list"
        url = self.baseListUrl+self.blackListUrl+str(1)
        request = Request(url,callback=self.parseBlackListUrls, meta = metadata, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        yield request

        # print "scraping disputes"
        # url = "https://tenders.procurement.gov.ge/dispute/engine/controller.php?action=search_app&page=1&pp=9999999"
        # request = Request(url,callback=self.parseDisputeLinks, cookies=self.sessionCookies, headers={"User-Agent":self.userAgent})
        # yield request


#ERROR HANDLING SECTION#
    def urlPageFailed(self,error):
        print "urlpager failed"
        yield error.request
        #requestFailure = [self.parseTenderUrls, error.request.url]
        #self.failedRequests.append(requestFailure)
    def tenderFailed(self,error):
        print "tender failed "
        requestFailure = [self.parseTender, error.request.url]
        self.failedRequests.append(requestFailure)
    def resultFailed(self,error):
        print "result failed"
        requestFailure = [self.parseResultsPage, error.request.url]
        self.failedRequests.append(requestFailure)
    def bidsFailed(self,error):
        print "bidder failed"
        requestFailure = [self.parseBidsPage, error.request.url]
        self.failedRequests.append(requestFailure)
    def documentationFailed(self,error):
        print "documentation failed"
        requestFailure = [self.parseDocumentationPage, error.request.url]
        self.failedRequests.append(requestFailure)
    def orgFailed(self,error):
        print "org failed failed"
        requestFailure = [self.parseOrganisation, error.request.url]
        self.failedRequests.append(requestFailure)
def main():
    # shut off log
    #from scrapy.conf import settings
    settings = get_project_settings()
    settings.overrides['LOG_ENABLED'] = False
 
    # set up crawler
    from scrapy.crawler import CrawlerProcess
     
    crawler = CrawlerProcess(settings)
    crawler.install()
    crawler.configure()
 
    def getSPACookies():
      #first get cookie from dummy request
      http = httplib2.Http()
      url = "https://tenders.procurement.gov.ge/public/?go=1000"
      headers={"User-Agent":'Mozilla/5.0 (Windows; U; MSIE 9.0; WIndows NT 9.0; en-US'}
      response, content = http.request(url, 'POST', headers=headers)
      cookies = {}
      if( response['set-cookie'] ):
          cookieString = response['set-cookie']
          print "COOKIE"
          print cookieString
          index = cookieString.find('SPALITE')
          index = cookieString.find("=",index)
          endIndex = cookieString.find(';',index)
          spaLite = cookieString[index+1:endIndex]
          cookies["SPALITE"] = spaLite
      
      url = "https://tenders.procurement.gov.ge/dispute/"
      headers={"User-Agent":'Mozilla/5.0 (Windows; U; MSIE 9.0; WIndows NT 9.0; en-US'}
      response, content = http.request(url, 'POST', headers=headers)
      if( response['set-cookie'] ):
          cookieString = response['set-cookie']
          print cookieString
          index = cookieString.find('DAVEBI')
          index = cookieString.find("=",index)
          endIndex = cookieString.find(';',index)
          davebi = cookieString[index+1:endIndex]
          cookies["DAVEBI"] = davebi
      return cookies

    cookies = getSPACookies()
    # schedule spider
    procurementSpider = ProcurementSpider()
    scrapeMode = "INCREMENTAL"
    if len(sys.argv) > 1:
      scrapeMode = sys.argv[1]

    print "Scrape mode is " + scrapeMode

    procurementSpider.setScrapeMode(scrapeMode)
    appPath = sys.argv[2]
    publicPath = "shared/system"
    outputPath = appPath+publicPath
    procurementSpider.tenderUpdatesFile = outputPath+"/liveTenders.txt"  
    
    procurementSpider.setSessionCookies(cookies)

    if procurementSpider.scrapeMode == "FIXERRORS":
      procurementSpider.fixpath = sys.argv[3]
    crawler.crawl(procurementSpider)

    #start engine scrapy/twisted
    print "STARTING ENGINE"
    crawler.start()
    print "MAIN SCRAPE COMPLETE"
      
    failFile = open(procurementSpider.scrapePath+"/failures.txt", 'wb')
    for failedRequest in procurementSpider.failedRequests:
        failFile.write(failedRequest[1])
        failFile.write("\n")
    failFile.close()

    #now make a copy of our scraped files and place them in the website folder and tell the web server to proc$
    currentPath = os.getcwd()
    os.chdir(appPath)

    fullPath = os.getcwd()+"/"+publicPath
    print "FULL PATH: "+fullPath
    for f in os.listdir(os.getcwd()+"/"+publicPath):
     print "remove: "+fullPath+"/"+f
     os.remove(fullPath+"/"+f)
    print os.getcwd()
    os.rmdir(os.getcwd()+"/"+publicPath)
    os.chdir(currentPath)
    print "coping from: "+procurementSpider.scrapePath
    print "to: "+outputPath
    shutil.copytree(procurementSpider.scrapePath, outputPath)
    
if __name__ == '__main__':
    main()
