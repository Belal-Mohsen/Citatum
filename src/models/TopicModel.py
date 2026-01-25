"""Topic data model for research topic data access"""
from sqlalchemy.future import select
from sqlalchemy import func
from .db_schemas.citatum.schemas.topic import Topic
from .BaseDataModel import BaseDataModel


class TopicModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object) -> "TopicModel":
        return cls(db_client=db_client)

    async def create_topic(self, topic: Topic) -> Topic:
        async with self.db_client() as session:
            session.add(topic)
            await session.commit()
            await session.refresh(topic)
            return topic

    async def get_topic_or_create(self, topic_name: str) -> Topic:
        async with self.db_client() as session:
            async with session.begin():
                query = select(Topic).where(Topic.topic_name == topic_name)
                topic = await session.execute(query)
                topic = topic.scalar_one_or_none()
                if topic is None:
                    topic_to_create = Topic(topic_name=topic_name)
                    topic_to_create = await self.create_topic(topic_to_create)
                    return topic_to_create
                else:
                    return topic

    async def get_topic_by_id(self, topic_id: str) -> Topic | None: 
        """
        Get topic by UUID.
        
        Args:
            topic_id: Topic UUID
        
        Returns:
            Topic instance or None if not found
        """
        async with self.db_client() as session:
            async with session.begin():
                query = select(Topic).where(Topic.topic_id == topic_id)
                topic = await session.execute(query)
                topic = topic.scalar_one_or_none()
                return topic
                      
    async def get_topic_by_name(self, topic_name: str) -> Topic | None:
        """
        Get topic by name.
        
        Args:
            topic_name: Topic name
        
        Returns:
            Topic instance or None if not found
        """
        async with self.db_client() as session:
            async with session.begin():
                query = select(Topic).where(Topic.topic_name == topic_name)
                topic = await session.execute(query)
                topic = topic.scalar_one_or_none()
                return topic

    async def get_all_topics(self, page: int = 1, page_size: int = 10) -> tuple[list[Topic], int]:
        """
        Get paginated topics with total count.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
        
        Returns:
            Tuple of (list of topics, total count)
        """
        async with self.db_client() as session:
            async with session.begin():
                # Get total count
                count_query = select(func.count(Topic.topic_id))
                count_result = await session.execute(count_query)
                total_count = count_result.scalar_one()
                
                # Get paginated topics
                offset = (page - 1) * page_size
                query = select(Topic).offset(offset).limit(page_size)
                result = await session.execute(query)
                topics = list(result.scalars().all())
                
                return topics, total_count
            
