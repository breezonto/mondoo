import logging.config
import yaml
import requests
import httpx
import datetime

from mcp.server.fastmcp     import FastMCP
from mondoo.configurator    import (AMAP_URI, AMAP_KEY)
from mondoo.mdo.core.common import setup_mcp_logging

config = setup_mcp_logging('kaleido')
logging.config.dictConfig(config)
logger = logging.getLogger('mondoo.mcp.server.kaleidoscope')

# Create server
mcp = FastMCP('kaleido')


# Define a tool
@mcp.tool()
def add(
    a : int,
    b : int
) -> int:
    """
Add two integers and return the sum.
Args:
    a: first number
    b: second number
    """
    return a + b


async def fetch_weather(city_code: str) -> dict:
    """Low-level API call"""
    params = {
        'city'       : city_code,
        'extensions' : 'all',
        'output'     : 'json',
        'key'        : AMAP_KEY
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(AMAP_URI, params=params)
        resp.raise_for_status()
        return resp.json()
    

def format_forecast(data: dict) -> str:
    forecast = data["forecasts"][0]
    province = forecast['province']
    city     = forecast['city']
    casts    = forecast['casts']

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    lines = [f"以下是{province}{city}的天气预报:\n"]
    lines.append(f"今天是{today}\n")
    
    for c in casts:
        lines.append(
            f"{c['date']}:\n"
            f"  白天: {c['dayweather']}, {c['daytemp']}°C\n"
            f"  晚上: {c['nightweather']}, {c['nighttemp']}°C\n"
        )
    
    return "".join(lines)


@mcp.tool()
async def get_weather(city_code: str) -> str:
    """获取某地未来几天的天气
Args:
    city_code: 查询的城市的对应的adcode城市编码

注意！：
    不要直接输入地名，给出目标地址所在城市编码（adcode），比如：
    北京市 - 11000
    北京市东城区 - 110101
    杭州市 - 330100
    杭州市上城区 - 330102
    """

    data = await fetch_weather(city_code)  # your httpx function

    if data.get('status') != '1':
        return f"API error: {data.get('info')}"
    try:
        return format_forecast(data)

    except Exception as e:
        return f"Parsing error: {str(e)}"


# Run server (stdio transport)
if __name__ == "__main__":
    mcp.run()