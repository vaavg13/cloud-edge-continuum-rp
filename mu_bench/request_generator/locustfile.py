import os
import random
from locust import HttpUser, User, task, between
from locust.env import Environment
from urllib.parse import urlparse

# Store generated user classes for Locust to find
# This list will be populated by configure_locust_users
USER_CLASSES = [] 

def configure_locust_users(app_definitions: list,
                           all_profiles_data: dict,
                           site_specific_dynamic_factor_calculator_func: callable):
    """
    Generates HttpUser classes. Each site a user targets will have its traffic 
    dynamically weighted based on its own configured seasonality and burst patterns.
    """
    global USER_CLASSES
    USER_CLASSES.clear()

    if not app_definitions:
        print("Warning: app_definitions is empty. No user classes will be generated.")
        return

    for app_conf in app_definitions:
        app_name = app_conf.get("name")
        app_user_weight = app_conf.get("user_weight", 1)
        target_sites_details = app_conf.get("targets", []) 
        app_port = app_conf.get("port")

        if not app_name or not target_sites_details:
            print(f"Warning: Skipping app '{app_name}' due to missing name or targets.")
            continue

        class_name_prefix = ''.join(word.capitalize() for word in app_name.replace('-', ' ').replace('_', ' ').split())
        dynamic_class_name = f"{class_name_prefix}User"

        class_attributes = {
            "app_name_static": app_name,
            "app_port_static": app_port,
            "target_sites_full_config_static": target_sites_details, # Has path, base_scale, random_range, pattern_config_refs
            "all_profiles_data_static": all_profiles_data,
            "site_factor_calculator_static": site_specific_dynamic_factor_calculator_func,
            "wait_time": app_conf.get("wait_time", between(0.5, 2)),
            "weight": app_user_weight, 
            "__module__": __name__
        }

        def __init__(self, environment: Environment):
            super(self.__class__, self).__init__(environment)
            self.app_name = self.__class__.app_name_static
            self.app_port = self.__class__.app_port_static
            self.target_sites_full_config = self.__class__.target_sites_full_config_static
            self.all_profiles_data = self.__class__.all_profiles_data_static
            self.site_factor_calculator = self.__class__.site_factor_calculator_static

            if self.app_port and self.environment.host:
                parsed_url = urlparse(self.environment.host)
                scheme = parsed_url.scheme
                netloc = parsed_url.netloc
                if netloc and ':' not in netloc:
                    self.host = f"{scheme}://{netloc}:{self.app_port}"

        @task(1)
        def perform_requests(self):
            if not hasattr(self.environment, 'shared_simulated_time'):
                return 
            
            current_simulated_time = self.environment.shared_simulated_time
            weighted_choices = []

            for site_detail in self.target_sites_full_config:
                site_path = site_detail.get("path")
                if not site_path:
                    continue

                site_pattern_refs = site_detail.get("pattern_config_refs") # This is crucial
                if not site_pattern_refs: # If a site has no patterns, its dynamic factor will be 1.0
                    site_dynamic_factor = 1.0
                else:
                    site_dynamic_factor = self.site_factor_calculator(
                        site_pattern_refs, # Pass the specific site's pattern choices
                        self.all_profiles_data,
                        current_simulated_time
                    )

                site_base_scale = float(site_detail.get("site_base_scale", 1.0))
                random_factor_min, random_factor_max = site_detail.get("site_random_factor_range", (1.0, 1.0))
                site_specific_scale_with_randomness = site_base_scale * random.uniform(random_factor_min, random_factor_max)
                
                dynamic_weight = site_dynamic_factor * site_specific_scale_with_randomness
                
                if dynamic_weight > 0:
                    weighted_choices.append({"path": site_path, "weight": dynamic_weight})
            
            if not weighted_choices:
                return

            population = [choice["path"] for choice in weighted_choices]
            weights = [choice["weight"] for choice in weighted_choices]
            chosen_path = random.choices(population=population, weights=weights, k=1)[0]
            request_name = f"{self.app_name}{chosen_path}"
            self.client.get(chosen_path, name=request_name)

        class_attributes["__init__"] = __init__
        class_attributes["perform_requests"] = perform_requests
        NewUserClass = type(dynamic_class_name, (HttpUser,), class_attributes)
        globals()[dynamic_class_name] = NewUserClass
        USER_CLASSES.append(NewUserClass)
        print(f"Successfully configured User class: {dynamic_class_name} for app '{app_name}' (App User Weight: {app_user_weight})")

    if not USER_CLASSES:
        print("Warning: No user classes created. Adding DummyUser.")
        class DummyUser(User):
            wait_time = between(1,2)
            weight = 1
            __module__ = __name__
            @task
            def dummy_task(self):
                pass # print("DummyUser task")
        globals()["DummyUser"] = DummyUser
        USER_CLASSES.append(DummyUser)