import discord, json
from discord.ext import commands

class _Deposit(commands.Cog, name="Economy"):
	
	def __init__(self, bot):
		self.bot = bot

	@commands.command(aliases=["dep"])
	async def deposit(self, ctx, amount: int):
			'''Save your money by depositing all the money in the bank'''
			with open('bank.json', encoding='utf-8') as f:
					bank = json.load(f)
			if amount < 0:
					await ctx.send(f'{ctx.author.mention} amount can not be negative')
			else:
					for current_user in bank['users']:
							if current_user['name'] == ctx.author.id:
									if (current_user['wallet'] - amount) < 0:
											await ctx.send(f'{ctx.author.mention} you do not have enough amount to deposit money')
									else:
											current_user['bank'] = current_user['bank'] + amount
											current_user['wallet'] = current_user['wallet'] - amount
											await ctx.send(f'{ctx.author.mention} deposited ' + str(amount) + ' money')
									break
					else:
							bank['users'].append({
									'name': ctx.author.id,
									'wallet': 400,
									'bank': 0
							})
							embed = discord.Embed(
									title=f"Balance of {ctx.author.name}",
									description="Welcome to Parrot Economy",
									colour=ctx.author.colour)
							embed.add_field(name="Wallet", value=400)
							embed.add_field(name="Bank", value=0)
							await ctx.send(embed=embed)
			with open('bank.json', 'w+') as f:
					json.dump(bank, f)

	@deposit.error
	async def deposit_error(self, ctx, error):
			if isinstance(error, commands.MissingRequiredArgument):
					await ctx.send('ERROR: MissingRequiredArgument. Please use proper syntax.\n```\n[p]deposit <amount:number>```')

def setup(bot):
	bot.add_cog(_Deposit(bot))