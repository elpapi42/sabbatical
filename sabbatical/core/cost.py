import logging

import databases
import litellm

logger = logging.getLogger(__name__)


async def sum_run_costs(db: databases.Database, **filters) -> dict:
    where_clauses = []
    values = {}
    for key, value in filters.items():
        where_clauses.append(f"{key} = :{key}")
        values[key] = value

    where = " AND ".join(where_clauses) if where_clauses else "1=1"

    row = await db.fetch_one(
        query=f"""
            SELECT COALESCE(SUM(consumed_input_tokens), 0) as input_tokens,
                   COALESCE(SUM(consumed_output_tokens), 0) as output_tokens,
                   COALESCE(SUM(total_cost), 0.0) as cost
            FROM runs
            WHERE {where}
        """,
        values=values,
    )

    return {
        "consumed_input_tokens": row["input_tokens"] if row else 0,
        "consumed_output_tokens": row["output_tokens"] if row else 0,
        "total_cost": row["cost"] if row else 0.0,
    }


async def organization_total_cost(db: databases.Database, org_name: str) -> dict:
    return await sum_run_costs(db, organization_name=org_name)


async def system_total_cost(db: databases.Database) -> dict:
    return await sum_run_costs(db)


def openrouter_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=f"openrouter/{model}",
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        )
        return prompt_cost + completion_cost
    except Exception:
        logger.warning("cost_per_token: no pricing data for model=%s, cost will be 0.0", model)
        return 0.0
