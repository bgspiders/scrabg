import scrapy


class ArticleItem(scrapy.Item):
    task_id = scrapy.Field()
    title = scrapy.Field()
    link = scrapy.Field()
    content = scrapy.Field()
    source_url = scrapy.Field()
    extra = scrapy.Field()

