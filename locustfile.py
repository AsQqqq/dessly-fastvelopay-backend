from locust import HttpUser, task, between

class MyUser(HttpUser):
    # wait_time = between(1, 5)

    @task
    def index(self):
        self.client.get(
            "/account/balance",
            headers={
                "Authorization": "Bearer c4cbf2ccef4c3de2dfecd9440b0aae46012c0f5c70f9236efa0c5c2ea0dba2fd",
                "Dessly-Token": "56b850b346564faa9b4cc2fe684da9bc"
            }
        )
        # self.client.get(
        #     "/ping"
        # )