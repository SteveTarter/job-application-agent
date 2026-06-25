#!/usr/bin/env python

import json
import sys


def search_company(company_name):
    # Pre-configured mocks for the companies mentioned in the design
    data = {
        "block": {
            "name": "Block (formerly Square / Cash App)",
            "industry": "Financial Technology (Fintech)",
            "context": "Block builds global payment infrastructure, Cash App, Square, and TBD. They have a strong emphasis on decentralization, cryptocurrency, and highly scalable distributed backend systems. Their stack heavily utilizes Go, Java, and cloud-native infrastructure.",
            "recent_news": "Continues focusing on payments scaling and expanding decentralized finance developer tools.",
        },
        "stripe": {
            "name": "Stripe",
            "industry": "Financial Infrastructure / Payments",
            "context": "Stripe operates payments infrastructure for the internet. Highly engineering-driven culture, prioritizing clean APIs, developer experience, and system reliability. Stack includes Ruby, Go, Java, and massive distributed data systems.",
            "recent_news": "Expanding Stripe Billing and enterprise payment integrations globally.",
        },
        "confluent": {
            "name": "Confluent",
            "industry": "Data Streaming / Event Brokerage",
            "context": "Confluent is built by the creators of Apache Kafka and offers a fully managed cloud-native event streaming platform. They focus on Kafka scaling, real-time data integration, and enterprise event meshes. Technical stack is primarily Java/Scala, Go, Kubernetes, and major cloud providers.",
            "recent_news": "Acquiring real-time Flink processing technologies and driving Confluent Cloud adoption.",
        },
    }

    normalized = company_name.lower().strip()
    match = None
    for k in data:
        if k in normalized:
            match = data[k]
            break

    if match:
        return match

    # Default fallback context for unknown companies
    return {
        "name": company_name,
        "industry": "Technology / Software",
        "context": f"{company_name} is a software/technology company specializing in modern digital platforms and services. Their engineering teams focus on scalability, reliability, and developer efficiency.",
        "recent_news": "Expanding their engineering capabilities and deploying cloud-native solutions.",
    }


if __name__ == "__main__":
    company_name = "Block"
    if len(sys.argv) > 1:
        company_name = sys.argv[1]

    result = search_company(company_name)
    print(json.dumps(result, indent=2))
