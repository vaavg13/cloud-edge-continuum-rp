from locust import HttpUser, task, between, TaskSet


class LightUser(HttpUser):
    wait_time = between(5, 15)  # Light users wait 5-15s between requests
    weight = 60  # 60% of users are LightUsers
    
    @task
    def get_s0(self):
        self.client.get("/s0")

class MediumUser(HttpUser):
    wait_time = between(2, 8)  # Medium users wait 2-8s between requests
    weight = 30  # 30% of users are MediumUsers
    
    @task(2)
    def get_s0(self):
        self.client.get("/s0")


class HeavyUser(HttpUser):
    wait_time = between(0.5, 3)  # Heavy users wait 0.5-3s between requests
    weight = 10  # 10% of users are HeavyUsers
    
    class HeavyUserTasks(TaskSet):
        @task(3)
        def get_s0(self):
            self.client.get("/s0")
    
    tasks = [HeavyUserTasks]

